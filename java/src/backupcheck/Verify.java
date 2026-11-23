package backupcheck;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.stream.Stream;

/**
 * Compares a source tree with its backup.
 *
 * Two modes exist because they answer different questions. Fast mode trusts size
 * and modification time, which is what most sync tools do; full mode hashes every
 * file whose size matches. A same-size byte flip is invisible to the first and
 * caught by the second, and the report says so instead of pretending otherwise.
 */
public final class Verify {
    record Meta(long size, long modified) {}

    record Issue(String kind, String path, long sourceSize, long backupSize) {}

    public static void main(String[] args) throws IOException, NoSuchAlgorithmException {
        Path source = Path.of("source");
        Path backup = Path.of("backup");
        Path out = Path.of("result.json");
        boolean full = true;
        int threads = 4;
        for (int index = 0; index < args.length; index++) {
            switch (args[index]) {
                case "--source" -> source = Path.of(args[++index]);
                case "--backup" -> backup = Path.of(args[++index]);
                case "--out" -> out = Path.of(args[++index]);
                case "--fast" -> full = false;
                case "--threads" -> threads = Integer.parseInt(args[++index]);
                default -> throw new IllegalArgumentException("unknown argument " + args[index]);
            }
        }

        long started = System.nanoTime();
        Map<String, Meta> sources = scan(source);
        Map<String, Meta> backups = scan(backup);

        List<Issue> issues = new ArrayList<>();
        List<String> toHash = new ArrayList<>();
        long bytes = 0;

        for (Map.Entry<String, Meta> entry : sources.entrySet()) {
            String path = entry.getKey();
            Meta left = entry.getValue();
            bytes += left.size();
            Meta right = backups.get(path);
            if (right == null) {
                issues.add(new Issue("missing", path, left.size(), -1));
            } else if (right.size() != left.size()) {
                issues.add(new Issue("size", path, left.size(), right.size()));
            } else if (full) {
                // Same size is not evidence of the same bytes: full mode hashes
                // every pair regardless of timestamp. Fast mode stops here.
                toHash.add(path);
            }
        }
        for (String path : backups.keySet()) {
            if (!sources.containsKey(path)) {
                issues.add(new Issue("extra", path, -1, backups.get(path).size()));
            }
        }

        if (full) {
            Map<String, String> sourceHashes = hashAll(source, toHash, threads);
            Map<String, String> backupHashes = hashAll(backup, toHash, threads);
            for (String path : toHash) {
                String left = sourceHashes.get(path);
                String right = backupHashes.get(path);
                if (left != null && right != null && !left.equals(right)) {
                    issues.add(new Issue("content", path, sources.get(path).size(), backups.get(path).size()));
                }
            }
        }

        issues.sort(Comparator.comparing(Issue::kind).thenComparing(Issue::path));
        Map<String, Integer> counts = new HashMap<>();
        for (Issue issue : issues) counts.merge(issue.kind(), 1, Integer::sum);
        double ms = (System.nanoTime() - started) / 1e6;

        StringBuilder json = new StringBuilder();
        json.append("{\"mode\":").append(quote(full ? "full" : "fast"))
            .append(",\"files\":").append(sources.size())
            .append(",\"bytes\":").append(bytes)
            .append(",\"hashed\":").append(full ? toHash.size() : 0)
            .append(",\"ms\":").append(String.format(Locale.ROOT, "%.1f", ms))
            .append(",\"counts\":{");
        int written = 0;
        for (Map.Entry<String, Integer> entry : counts.entrySet()) {
            if (written++ > 0) json.append(',');
            json.append(quote(entry.getKey())).append(':').append(entry.getValue());
        }
        json.append("},\"issues\":[");
        for (int index = 0; index < issues.size(); index++) {
            Issue issue = issues.get(index);
            if (index > 0) json.append(',');
            json.append("{\"kind\":").append(quote(issue.kind()))
                .append(",\"path\":").append(quote(issue.path()))
                .append(",\"source_size\":").append(issue.sourceSize())
                .append(",\"backup_size\":").append(issue.backupSize())
                .append('}');
        }
        json.append("]}\n");
        Files.createDirectories(out.toAbsolutePath().getParent());
        Files.writeString(out, json.toString(), StandardCharsets.UTF_8);

        System.out.printf(Locale.ROOT,
            "%s: %d files, %.1f MB, %d issues in %.1f ms (%d hashed)%n",
            full ? "full" : "fast", sources.size(), bytes / 1e6, issues.size(), ms,
            full ? toHash.size() : 0);
    }

    private static Map<String, Meta> scan(Path root) throws IOException {
        Map<String, Meta> files = new HashMap<>();
        if (!Files.isDirectory(root)) return files;
        try (Stream<Path> stream = Files.walk(root)) {
            for (Path path : stream.filter(Files::isRegularFile).toList()) {
                String relative = root.relativize(path).toString().replace('\\', '/');
                files.put(relative, new Meta(Files.size(path), Files.getLastModifiedTime(path).toMillis()));
            }
        }
        return files;
    }

    private static Map<String, String> hashAll(Path root, List<String> paths, int threads)
            throws IOException, NoSuchAlgorithmException {
        Map<String, String> hashes = new HashMap<>();
        ExecutorService executor = Executors.newFixedThreadPool(Math.max(1, threads));
        List<Future<?>> futures = new ArrayList<>();
        for (String path : paths) {
            futures.add(executor.submit(() -> {
                String digest = sha256(root.resolve(path));
                synchronized (hashes) {
                    hashes.put(path, digest);
                }
                return null;
            }));
        }
        for (Future<?> future : futures) {
            try {
                future.get();
            } catch (Exception error) {
                throw new IOException("hashing failed", error);
            }
        }
        executor.shutdown();
        return hashes;
    }

    private static String sha256(Path path) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = Files.newInputStream(path)) {
                byte[] buffer = new byte[1 << 16];
                int read;
                while ((read = input.read(buffer)) > 0) {
                    digest.update(buffer, 0, read);
                }
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException error) {
            throw new IOException(error);
        }
    }

    private static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (int index = 0; index < value.length(); index++) {
            char c = value.charAt(index);
            if (c == '"' || c == '\\') out.append('\\');
            out.append(c);
        }
        return out.append('"').toString();
    }
}
