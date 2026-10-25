/* Original application code, Copyright 2026 TheOutlandsDev and contributors. MIT. */
import java.awt.*;
import java.awt.event.*;
import java.io.*;
import java.math.BigInteger;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.*;
import java.time.Instant;
import java.util.List;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import java.util.regex.Pattern;
import javax.swing.*;
import javax.swing.table.*;

/** Read-only, explicit-folder inventories and SHA-256 duplicate candidates. */
public final class FileAudit {
    static final String VERSION = "1.0.0";
    static final LinkOption[] NOFOLLOW = {LinkOption.NOFOLLOW_LINKS};
    static final long MIB = 1024L * 1024;
    static final int MAX_REPORT_BYTES = 16 * 1024 * 1024;

    public record Config(Path root, boolean hashes, Set<String> extensions, int maxFiles,
                         int maxEntries, long maxFileBytes, long maxHashBytes,
                         int maxDepth, long maxMillis) {
        public Config {
            Objects.requireNonNull(root);
            root = root.toAbsolutePath().normalize();
            extensions = Set.copyOf(extensions);
            if (root.toString().startsWith("\\\\") || maxFiles < 1 || maxFiles > 20000
                || maxEntries < 1 || maxEntries > 100000 || maxFileBytes < 1 || maxFileBytes > 10240 * MIB
                || maxHashBytes < 1 || maxHashBytes > 102400 * MIB || maxDepth < 1 || maxDepth > 128
                || maxMillis < 1 || maxMillis > 3600000 || extensions.size() > 32)
                throw new IllegalArgumentException("Invalid scan limits or non-local root.");
            for (String ext : extensions)
                if (!ext.matches("\\.[a-z0-9_+-]{1,20}")) throw new IllegalArgumentException("Invalid extension filter.");
        }
        static Config defaults(Path root) {
            return new Config(root, true, Set.of(), 10000, 20000, 256 * MIB, 2048 * MIB, 64, 300000);
        }
    }

    public record Entry(String path, long bytes, String modifiedUtc, String sha256,
                        String hashStatus, Object identity) {
        Map<String,Object> data() {
            return object("path", path, "bytes", bytes, "modified_utc", modifiedUtc,
                          "sha256", sha256, "hash_status", hashStatus);
        }
    }
    public record Issue(String path, String code) {
        Map<String,Object> data() { return object("path", path, "code", code); }
    }
    public record Group(long bytesPerFile, String sha256, List<String> paths, boolean identityKnown) {
        Map<String,Object> data() { return object("bytes_per_file", bytesPerFile, "sha256", sha256,
                                                "paths", paths, "file_identity_available", identityKnown); }
    }
    public record Progress(int files, long bytesRead, int entries) {}

    public static final class Report {
        String started = Instant.now().toString(), ended;
        String status = "complete";
        boolean simulated;
        final Config config;
        final List<Entry> files = new ArrayList<>();
        final List<Issue> issues = new ArrayList<>();
        List<Group> groups = List.of();
        long bytesRead;
        BigInteger totalFileBytes = BigInteger.ZERO;
        int entries, issueCount, hardLinkAliases;
        Report(Config config) { this.config = config; }
        void issue(String path, String code) {
            issueCount++;
            if (issues.size() < 1000) issues.add(new Issue(path, code));
            if (!status.equals("cancelled")) status = "partial";
        }
        Map<String,Object> data() {
            List<String> filters = new ArrayList<>(config.extensions()); Collections.sort(filters);
            return object("schema", "outlands-file-audit/1", "app_version", VERSION,
                "simulated", simulated, "started_utc", started, "ended_utc", ended,
                "status", status, "hash_algorithm", config.hashes() ? "SHA-256" : null,
                "scope", "Explicit selected folder; relative paths; no followed links; best-effort change checks",
                "extensions", filters,
                "limits", object("max_files", config.maxFiles(), "max_entries", config.maxEntries(),
                    "max_file_bytes", config.maxFileBytes(), "max_hash_bytes", config.maxHashBytes(),
                    "max_depth", config.maxDepth(), "cooperative_time_limit_ms", config.maxMillis()),
                "summary", object("files", files.size(), "file_bytes_observed", totalFileBytes,
                    "bytes_hashed", bytesRead, "entries_visited", entries, "issue_count", issueCount,
                    "issues_omitted", issueCount - issues.size(), "duplicate_candidate_groups", groups.size(),
                    "hard_link_aliases_excluded_from_groups", hardLinkAliases),
                "files", files.stream().map(Entry::data).toList(),
                "duplicate_candidates", groups.stream().map(Group::data).toList(),
                "issues", issues.stream().map(Issue::data).toList(),
                "privacy", object("absolute_root_included", false, "file_contents_included", false,
                                  "automatic_upload", false),
                "interpretation", "Not malware/cheat detection, deletion advice, an atomic snapshot or proof of physical storage savings.");
        }
    }

    static BasicFileAttributes attributes(Path p) throws IOException {
        return Files.readAttributes(p, BasicFileAttributes.class, NOFOLLOW);
    }
    static boolean plain(BasicFileAttributes a) { return !a.isSymbolicLink() && !a.isOther(); }
    static boolean stable(BasicFileAttributes a, BasicFileAttributes b) {
        return a.isRegularFile() && b.isRegularFile() && plain(b) && a.size() == b.size()
            && a.lastModifiedTime().equals(b.lastModifiedTime()) && Objects.equals(a.fileKey(), b.fileKey());
    }
    /** Compare no-follow and resolved paths to reject existing junctions as well as symlinks. */
    static void checkComponent(Path p) throws IOException {
        BasicFileAttributes a = attributes(p);
        if (!plain(a) || !p.toRealPath(LinkOption.NOFOLLOW_LINKS).equals(p.toRealPath()))
            throw new IOException("linked_or_special_path");
    }
    static void checkAncestors(Path path) throws IOException {
        Path p = path.toAbsolutePath().normalize(), current = p.getRoot();
        checkComponent(current);
        for (Path part : p) { current = current.resolve(part); checkComponent(current); }
    }
    static String relative(Path root, Path p) { return root.relativize(p).toString().replace(File.separatorChar, '/'); }
    static boolean selected(String filename, Set<String> extensions) {
        if (extensions.isEmpty()) return true;
        int dot = filename.lastIndexOf('.');
        return dot >= 0 && extensions.contains(filename.substring(dot).toLowerCase(Locale.ROOT));
    }

    public static Report scan(Config cfg, AtomicBoolean cancel, Consumer<Progress> progress) throws IOException {
        return scan(cfg, cancel, progress, p -> {});
    }
    /** The hook supports controlled mutation fixtures; production supplies a no-op. */
    static Report scan(Config cfg, AtomicBoolean cancel, Consumer<Progress> progress, Consumer<Path> beforeRead) throws IOException {
        checkAncestors(cfg.root());
        if (!attributes(cfg.root()).isDirectory()) throw new IOException("directory_required");
        Report report = new Report(cfg);
        long start = System.nanoTime();
        Set<Object> visitedDirectories = new HashSet<>();
        class Visitor extends SimpleFileVisitor<Path> {
            long pathCharacters;
            boolean stopped() {
                if (cancel.get() || Thread.currentThread().isInterrupted()) {
                    if (!report.status.equals("cancelled")) report.issue("", "cancelled");
                    report.status = "cancelled"; return true;
                }
                if ((System.nanoTime() - start) / 1000000 >= cfg.maxMillis()) {
                    report.issue("", "time_limit"); return true;
                }
                return false;
            }
            boolean visit(Path p) {
                if (stopped()) return false;
                if (report.entries >= cfg.maxEntries()) { report.issue("", "entry_limit"); return false; }
                report.entries++;
                String rel = relative(cfg.root(), p);
                pathCharacters += rel.length();
                if (rel.length() > 2048 || pathCharacters > 2000000) {
                    report.issue("", "path_text_limit"); return false;
                }
                return true;
            }
            @Override public FileVisitResult preVisitDirectory(Path p, BasicFileAttributes a) {
                if (!visit(p)) return FileVisitResult.TERMINATE;
                try {
                    checkAncestors(p);
                    if (a.fileKey() != null && !visitedDirectories.add(a.fileKey())) {
                        report.issue(relative(cfg.root(), p), "directory_alias"); return FileVisitResult.SKIP_SUBTREE;
                    }
                    return FileVisitResult.CONTINUE;
                } catch (IOException | SecurityException e) {
                    report.issue(relative(cfg.root(), p), "linked_or_unreadable_directory");
                    return FileVisitResult.SKIP_SUBTREE;
                }
            }
            @Override public FileVisitResult visitFile(Path p, BasicFileAttributes a) {
                if (!visit(p)) return FileVisitResult.TERMINATE;
                String rel = relative(cfg.root(), p);
                if (a.isDirectory()) { report.issue(rel, "depth_limit"); return FileVisitResult.CONTINUE; }
                if (!plain(a) || !a.isRegularFile()) { report.issue(rel, "linked_or_special_file"); return FileVisitResult.CONTINUE; }
                if (!selected(p.getFileName().toString(), cfg.extensions())) return FileVisitResult.CONTINUE;
                if (report.files.size() >= cfg.maxFiles()) { report.issue("", "file_limit"); return FileVisitResult.TERMINATE; }
                String hash = null, state = cfg.hashes() ? "hashed" : "metadata_only";
                try {
                    checkAncestors(p);
                    BasicFileAttributes before = attributes(p);
                    if (!stable(a, before)) throw new IOException("changed");
                    if (cfg.hashes() && before.size() > cfg.maxFileBytes()) {
                        state = "file_size_limit"; report.issue(rel, state);
                    } else if (cfg.hashes() && before.size() > cfg.maxHashBytes() - report.bytesRead) {
                        state = "hash_byte_limit"; report.issue(rel, state);
                    } else if (cfg.hashes()) {
                        beforeRead.accept(p);
                        checkAncestors(p);
                        MessageDigest digest = sha256();
                        Set<OpenOption> options = new HashSet<>();
                        options.add(StandardOpenOption.READ); options.add(LinkOption.NOFOLLOW_LINKS);
                        try (SeekableByteChannel channel = Files.newByteChannel(p, options)) {
                            if (channel.size() != before.size()) throw new IOException("changed");
                            long read = 0;
                            ByteBuffer buffer = ByteBuffer.allocate(65536);
                            while (read < before.size()) {
                                if (stopped()) { state = "cancelled_or_timed_out"; break; }
                                buffer.clear(); buffer.limit((int)Math.min(buffer.capacity(), before.size() - read));
                                int count = channel.read(buffer);
                                if (count < 0) throw new IOException("changed");
                                read += count; report.bytesRead += count;
                                buffer.flip(); digest.update(buffer);
                            }
                            if (state.equals("hashed")) {
                                checkAncestors(p);
                                if (channel.size() != before.size() || !stable(before, attributes(p))) throw new IOException("changed");
                                hash = HexFormat.of().formatHex(digest.digest());
                            }
                        }
                    }
                    report.files.add(new Entry(rel, before.size(), before.lastModifiedTime().toInstant().toString(), hash, state, before.fileKey()));
                } catch (IOException | SecurityException | UnsupportedOperationException e) {
                    state = "changed_or_unreadable"; report.issue(rel, state);
                    report.files.add(new Entry(rel, a.size(), a.lastModifiedTime().toInstant().toString(), null, state, null));
                }
                progress.accept(new Progress(report.files.size(), report.bytesRead, report.entries));
                return stopped() ? FileVisitResult.TERMINATE : FileVisitResult.CONTINUE;
            }
            @Override public FileVisitResult visitFileFailed(Path p, IOException e) {
                if (!visit(p)) return FileVisitResult.TERMINATE;
                report.issue(relative(cfg.root(), p), "unreadable_entry"); return FileVisitResult.CONTINUE;
            }
            @Override public FileVisitResult postVisitDirectory(Path p, IOException e) {
                if (e != null) report.issue(relative(cfg.root(), p), "directory_listing_failed");
                return stopped() ? FileVisitResult.TERMINATE : FileVisitResult.CONTINUE;
            }
        }
        try {
            Files.walkFileTree(cfg.root(), Set.of(), cfg.maxDepth(), new Visitor());
        } catch (IOException | SecurityException e) {
            report.issue("", "traversal_failed");
        }
        report.files.sort(Comparator.comparing(Entry::path));
        for (Entry entry : report.files) report.totalFileBytes = report.totalFileBytes.add(BigInteger.valueOf(entry.bytes()));
        findGroups(report);
        report.ended = Instant.now().toString();
        return report;
    }

    static MessageDigest sha256() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
    }
    static void findGroups(Report report) {
        Map<String,List<Entry>> candidates = new TreeMap<>();
        for (Entry entry : report.files)
            if (entry.sha256() != null && entry.bytes() > 0)
                candidates.computeIfAbsent(entry.bytes() + ":" + entry.sha256(), ignored -> new ArrayList<>()).add(entry);
        List<Group> groups = new ArrayList<>();
        for (List<Entry> values : candidates.values()) {
            Set<Object> identities = new HashSet<>(); List<String> paths = new ArrayList<>(); boolean known = true;
            for (Entry entry : values) {
                if (entry.identity() == null) known = false;
                if (entry.identity() != null && !identities.add(entry.identity())) { report.hardLinkAliases++; continue; }
                paths.add(entry.path());
            }
            if (paths.size() > 1) groups.add(new Group(values.get(0).bytes(), values.get(0).sha256(), List.copyOf(paths), known));
        }
        groups.sort(Comparator.comparingLong(Group::bytesPerFile).reversed().thenComparing(Group::sha256));
        report.groups = List.copyOf(groups);
    }

    static Set<String> parseExtensions(String text) {
        if (text.isBlank()) return Set.of();
        Set<String> result = new TreeSet<>();
        for (String part : text.split(",", -1)) {
            String ext = part.trim().toLowerCase(Locale.ROOT);
            if (!ext.matches("\\.[a-z0-9_+-]{1,20}")) throw new IllegalArgumentException("Use comma-separated extensions, such as .txt,.json.");
            result.add(ext);
        }
        if (result.size() > 32) throw new IllegalArgumentException("Too many extension filters.");
        return result;
    }
    static Map<String,Object> object(Object... pairs) {
        Map<String,Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String)pairs[i], pairs[i + 1]);
        return result;
    }
    static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof Boolean || value instanceof Integer || value instanceof Long || value instanceof BigInteger) return value.toString();
        if (value instanceof String text) {
            StringBuilder out = new StringBuilder("\"");
            for (char c : text.toCharArray()) {
                if (c == '"' || c == '\\') out.append('\\').append(c);
                else if (c < 32 || Character.isSurrogate(c)) out.append(String.format(Locale.ROOT, "\\u%04x", (int)c));
                else out.append(c);
            }
            return out.append('"').toString();
        }
        if (value instanceof Map<?,?> map) {
            StringJoiner out = new StringJoiner(",", "{", "}");
            for (var e : map.entrySet()) out.add(json(e.getKey()) + ":" + json(e.getValue()));
            return out.toString();
        }
        if (value instanceof Collection<?> list) {
            StringJoiner out = new StringJoiner(",", "[", "]");
            for (Object element : list) out.add(json(element));
            return out.toString();
        }
        throw new IllegalArgumentException("Unsupported JSON value");
    }
    static byte[] reportBytes(Report report) throws IOException {
        byte[] data = (json(report.data()) + "\n").getBytes(StandardCharsets.UTF_8);
        if (data.length > MAX_REPORT_BYTES) throw new IOException("report_size_limit");
        return data;
    }
    static Path checkOutput(Path chosen, Path root) throws IOException {
        Path output = chosen.toAbsolutePath().normalize();
        if (!output.getFileName().toString().toLowerCase(Locale.ROOT).endsWith(".json")
            || Files.exists(output, NOFOLLOW) || output.toString().startsWith("\\\\")) throw new IOException("new_local_json_required");
        checkAncestors(output.getParent());
        if (!attributes(output.getParent()).isDirectory()) throw new IOException("directory_required");
        if (root != null) {
            checkAncestors(root);
            Path realOutput = output.getParent().toRealPath().resolve(output.getFileName());
            if (realOutput.startsWith(root.toRealPath())) throw new IOException("output_inside_input");
        }
        return output;
    }
    static void save(Path chosen, Report report) throws IOException {
        Path output = checkOutput(chosen, report.simulated ? null : report.config.root());
        byte[] data = reportBytes(report);
        // Deliberate exclusive creation; a disk error can leave an incomplete new file.
        try (OutputStream stream = Files.newOutputStream(output, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            stream.write(data);
        }
    }

    static Report demo() {
        Config config = Config.defaults(Path.of(".")); Report report = new Report(config); report.simulated = true;
        report.started = "2026-01-01T00:00:00Z"; report.ended = "2026-01-01T00:00:01Z";
        String digest = HexFormat.of().formatHex(sha256().digest("fictional sample\n".getBytes(StandardCharsets.UTF_8)));
        report.files.add(new Entry("notes/alpha.txt", 17, report.started, digest, "hashed", "fictional-a"));
        report.files.add(new Entry("copies/alpha-copy.txt", 17, report.started, digest, "hashed", "fictional-b"));
        report.files.add(new Entry("empty.txt", 0, report.started, HexFormat.of().formatHex(sha256().digest(new byte[0])), "hashed", "fictional-c"));
        report.files.sort(Comparator.comparing(Entry::path)); report.totalFileBytes = BigInteger.valueOf(34); report.bytesRead = 34; report.entries = 5;
        findGroups(report); return report;
    }

    @FunctionalInterface interface ScanTask {
        Report run(Config config, AtomicBoolean cancel, Consumer<Progress> progress) throws IOException;
    }
    public static final class Window extends JFrame {
        private static final long serialVersionUID = 1L;
        final ScanTask scanner;
        final JTextField root = new JTextField(55), extensions = new JTextField(18), search = new JTextField(22);
        final JCheckBox hashes = new JCheckBox("SHA-256 and duplicate candidates (reads file contents)", true);
        final JSpinner maxFiles = spinner(10000, 1, 20000), maxEntries = spinner(20000, 1, 100000),
            perFile = spinner(256, 1, 10240), totalHash = spinner(2048, 1, 102400),
            depth = spinner(64, 1, 128), seconds = spinner(300, 1, 3600);
        final JButton browse = new JButton("Choose folder"), start = new JButton("Start audit"),
            stop = new JButton("Stop"), demo = new JButton("Try demo (no file access)"), export = new JButton("Save JSON report");
        final JLabel status = new JLabel("Ready. No folder has been scanned.");
        final DefaultTableModel files = model(new String[]{"Relative path", "Bytes", "Hash status", "SHA-256"}, 1),
            duplicates = model(new String[]{"Bytes per file", "Paths", "SHA-256", "Relative paths"}, 0),
            issues = model(new String[]{"Relative path", "Reason"}, -1);
        final JTable fileTable = table(files), groupTable = table(duplicates), issueTable = table(issues);
        final List<JComponent> inputs = new ArrayList<>();
        final AtomicBoolean cancel = new AtomicBoolean();
        volatile boolean busy;
        Thread worker;
        Report report;
        Window() { this(FileAudit::scan); }
        Window(ScanTask scanner) {
            super("Outlands File Audit");
            this.scanner = scanner;
            setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);
            JPanel outer = new JPanel(new BorderLayout(10, 10)); outer.setBorder(BorderFactory.createEmptyBorder(14,14,14,14));
            JPanel top = new JPanel(); top.setLayout(new BoxLayout(top, BoxLayout.Y_AXIS));
            JLabel title = new JLabel("File Audit"); title.setFont(title.getFont().deriveFont(Font.BOLD, 24)); top.add(title);
            top.add(new JLabel("Inventory one chosen folder. No deletion, malware verdicts, background monitoring or uploads."));
            JPanel folder = new JPanel(new BorderLayout(6, 0)); folder.add(root, BorderLayout.CENTER); folder.add(browse, BorderLayout.EAST); top.add(folder);
            JPanel options = new JPanel(new FlowLayout(FlowLayout.LEFT)); options.add(hashes); options.add(new JLabel("Extensions (blank = all)")); options.add(extensions); top.add(options);
            JPanel limits = new JPanel(new GridLayout(2, 6, 8, 3));
            for (String label : new String[]{"Max files", "Max entries", "Max file MiB", "Hash budget MiB", "Max depth", "Time limit (s)"}) limits.add(new JLabel(label));
            for (JSpinner field : new JSpinner[]{maxFiles,maxEntries,perFile,totalHash,depth,seconds}) limits.add(field);
            top.add(limits);
            JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT));
            for (JButton b : new JButton[]{start,stop,demo,export}) actions.add(b);
            top.add(actions); top.add(status); outer.add(top, BorderLayout.NORTH);
            JPanel inventory = new JPanel(new BorderLayout()); JPanel find = new JPanel(new FlowLayout(FlowLayout.LEFT));
            fileTable.setAutoResizeMode(JTable.AUTO_RESIZE_OFF);
            groupTable.setAutoResizeMode(JTable.AUTO_RESIZE_OFF);
            int[] fileWidths = {410,110,180,520}, groupWidths = {120,75,520,650};
            for(int i=0;i<fileWidths.length;i++)fileTable.getColumnModel().getColumn(i).setPreferredWidth(fileWidths[i]);
            for(int i=0;i<groupWidths.length;i++)groupTable.getColumnModel().getColumn(i).setPreferredWidth(groupWidths[i]);
            find.add(new JLabel("Filter displayed rows")); find.add(search); inventory.add(find, BorderLayout.NORTH); inventory.add(new JScrollPane(fileTable), BorderLayout.CENTER);
            JTabbedPane tabs = new JTabbedPane(); tabs.addTab("Files", inventory); tabs.addTab("Duplicate candidates", new JScrollPane(groupTable)); tabs.addTab("Issues / exclusions", new JScrollPane(issueTable));
            outer.add(tabs, BorderLayout.CENTER);
            outer.add(new JLabel("Reports contain relative filenames, metadata and optional hashes. Review them before sharing. Export must be outside the input folder."), BorderLayout.SOUTH);
            setContentPane(outer); setSize(1150,760); setMinimumSize(new Dimension(950,620)); setLocationByPlatform(true);
            stop.setEnabled(false); export.setEnabled(false);
            inputs.addAll(List.of(root,extensions,hashes,maxFiles,maxEntries,perFile,totalHash,depth,seconds,browse,start,demo));
            browse.addActionListener(e -> { JFileChooser chooser = new JFileChooser(); chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY); if (chooser.showOpenDialog(this)==JFileChooser.APPROVE_OPTION) root.setText(chooser.getSelectedFile().toString()); });
            start.addActionListener(e -> begin()); stop.addActionListener(e -> requestStop());
            demo.addActionListener(e -> { if (!busy) display(FileAudit.demo()); });
            export.addActionListener(e -> saveReport());
            search.getDocument().addDocumentListener(new javax.swing.event.DocumentListener() {
                public void insertUpdate(javax.swing.event.DocumentEvent e) { filter(); }
                public void removeUpdate(javax.swing.event.DocumentEvent e) { filter(); }
                public void changedUpdate(javax.swing.event.DocumentEvent e) { filter(); }
            });
            addWindowListener(new WindowAdapter() { @Override public void windowClosing(WindowEvent e) { requestStop(); dispose(); } });
        }
        static JSpinner spinner(int value,int min,int max) { return new JSpinner(new SpinnerNumberModel(value,min,max,1)); }
        static DefaultTableModel model(String[] names, int numeric) {
            return new DefaultTableModel(names,0) {
                @Override public boolean isCellEditable(int row,int col) { return false; }
                @Override public Class<?> getColumnClass(int col) { return col==numeric ? Long.class : String.class; }
            };
        }
        static JTable table(DefaultTableModel model) {
            JTable result = new JTable(model); result.setAutoCreateRowSorter(true); result.setFillsViewportHeight(true);
            DefaultTableCellRenderer plain = new DefaultTableCellRenderer(); plain.putClientProperty("html.disable", Boolean.TRUE);
            result.setDefaultRenderer(Object.class,plain);
            return result;
        }
        void filter() {
            @SuppressWarnings("unchecked") TableRowSorter<DefaultTableModel> sorter=(TableRowSorter<DefaultTableModel>)fileTable.getRowSorter();
            sorter.setRowFilter(search.getText().isEmpty() ? null : RowFilter.regexFilter("(?iu)"+Pattern.quote(search.getText())));
        }
        Config settings() {
            if (root.getText().isBlank()) throw new IllegalArgumentException("Choose a folder first.");
            for (JSpinner field : new JSpinner[]{maxFiles,maxEntries,perFile,totalHash,depth,seconds})
                try { field.commitEdit(); } catch (java.text.ParseException e) { throw new IllegalArgumentException("Check the scan limits."); }
            return new Config(Path.of(root.getText()), hashes.isSelected(), parseExtensions(extensions.getText()),
                (int)maxFiles.getValue(),(int)maxEntries.getValue(),(int)perFile.getValue()*MIB,
                (int)totalHash.getValue()*MIB,(int)depth.getValue(),(int)seconds.getValue()*1000L);
        }
        void begin() {
            if (busy) return;
            final Config config;
            try { config=settings(); } catch (IllegalArgumentException e) { JOptionPane.showMessageDialog(this,"Choose a valid local folder and check the numeric limits/extensions.","Check settings",JOptionPane.ERROR_MESSAGE); return; }
            busy=true; cancel.set(false); inputs.forEach(x->x.setEnabled(false)); stop.setEnabled(true); export.setEnabled(false);
            status.setText("Auditing the selected folder. Source files are read only.");
            worker=new Thread(() -> {
                try {
                    Report result=scanner.run(config,cancel,p->{ if(p.files()%20==0) SwingUtilities.invokeLater(()->{ if(busy&&!cancel.get())status.setText("Auditing: "+p.files()+" files; "+p.bytesRead()+" bytes hashed."); }); });
                    SwingUtilities.invokeLater(()->finish(result));
                } catch (IOException | RuntimeException e) {
                    SwingUtilities.invokeLater(()->{ finish(null); status.setText("The folder could not be audited. Check access, links and availability; no raw error paths were retained."); });
                }
            },"file-audit-worker"); worker.setDaemon(true); worker.start();
        }
        void requestStop() { cancel.set(true); if(worker!=null&&worker.isAlive())worker.interrupt(); if(busy){stop.setEnabled(false); status.setText("Stopping… waiting for the current filesystem operation. You may close the app if it is blocked.");} }
        void finish(Report result) {
            busy=false; inputs.forEach(x->x.setEnabled(true)); stop.setEnabled(false);
            if(result!=null)display(result); else export.setEnabled(report!=null);
        }
        void display(Report value) {
            report=value;
            files.setRowCount(0); duplicates.setRowCount(0); issues.setRowCount(0);
            for(Entry e:value.files) files.addRow(new Object[]{e.path(),e.bytes(),e.hashStatus(),e.sha256()});
            for(Group g:value.groups) duplicates.addRow(new Object[]{g.bytesPerFile(),Integer.toString(g.paths().size()),g.sha256(),String.join(" | ",g.paths())});
            for(Issue e:value.issues)issues.addRow(new Object[]{e.path(),e.code()});
            status.setText((value.simulated?"DEMO — ":"")+value.status+": "+value.files.size()+" files; "+value.groups.size()+" duplicate candidate groups; "+value.issueCount+" issues. No source files changed.");
            export.setEnabled(true);
        }
        void saveReport() {
            if(report==null||busy)return;
            JFileChooser chooser=new JFileChooser(); chooser.setSelectedFile(new File("file-audit-report.json"));
            if(chooser.showSaveDialog(this)==JFileChooser.APPROVE_OPTION)
                try { save(chooser.getSelectedFile().toPath(),report); status.setText("New report saved locally. Source files were not changed."); }
                catch(IOException | RuntimeException e) { JOptionPane.showMessageDialog(this,"Choose a new .json file outside the input folder, under an existing writable non-linked directory. Reports are limited to 16 MiB; reduce the scan scope if needed. An I/O failure can leave an incomplete newly created report.","Report not saved",JOptionPane.ERROR_MESSAGE); }
        }
    }

    static void help(PrintStream out) {
        out.println("Outlands File Audit 1.0.0 — Java 17; MIT; read-only source-folder audit\n"
            +"No arguments: desktop app. --demo: fictional JSON, no folder access.\n"
            +"--root FOLDER [--metadata-only] [--ext .txt,.json] [--output NEW.json]\n"
            +"--max-files 10000 --max-entries 20000 --max-file-mib 256 --max-hash-mib 2048\n"
            +"--max-depth 64 --seconds 300\n"
            +"Limits are cooperative; blocked filesystem calls are not forcibly timed out.\n"
            +"No links followed, deletion, malware verdicts, or automatic upload.");
    }
    static int cli(String[] args, PrintStream out, PrintStream err) {
        try {
            Map<String,String> options=new HashMap<>(); boolean demo=false,metadata=false;
            Set<String> valued=Set.of("--root","--ext","--output","--max-files","--max-entries","--max-file-mib","--max-hash-mib","--max-depth","--seconds");
            for(int i=0;i<args.length;i++) {
                String key=args[i];
                if(key.equals("--help")){help(out);return 0;}
                if(key.equals("--demo")){if(demo)throw new IllegalArgumentException();demo=true;}
                else if(key.equals("--metadata-only")){if(metadata)throw new IllegalArgumentException();metadata=true;}
                else if(valued.contains(key)&&i+1<args.length&&!options.containsKey(key))options.put(key,args[++i]);
                else throw new IllegalArgumentException();
            }
            if(demo&&(metadata||options.keySet().stream().anyMatch(k->!k.equals("--output"))))throw new IllegalArgumentException();
            Report report;
            Path output=options.containsKey("--output")?Path.of(options.get("--output")):null;
            if(demo) { if(output!=null)checkOutput(output,null); report=demo(); }
            else {
                if(!options.containsKey("--root"))throw new IllegalArgumentException();
                Config cfg=new Config(Path.of(options.get("--root")),!metadata,parseExtensions(options.getOrDefault("--ext","")),
                    Integer.parseInt(options.getOrDefault("--max-files","10000")),Integer.parseInt(options.getOrDefault("--max-entries","20000")),
                    Math.multiplyExact(Long.parseLong(options.getOrDefault("--max-file-mib","256")),MIB),
                    Math.multiplyExact(Long.parseLong(options.getOrDefault("--max-hash-mib","2048")),MIB),
                    Integer.parseInt(options.getOrDefault("--max-depth","64")),Math.multiplyExact(Long.parseLong(options.getOrDefault("--seconds","300")),1000));
                if(output!=null)checkOutput(output,cfg.root());
                report=scan(cfg,new AtomicBoolean(),p->{});
            }
            if(output!=null)save(output,report);
            out.write(reportBytes(report));
            return report.status.equals("complete")?0:report.status.equals("cancelled")?130:2;
        } catch (IOException | RuntimeException e) {
            err.println("File Audit could not complete: invalid settings, unavailable/linked input, or unsafe/unwritable output. Use --help. A newly created report may be incomplete after an I/O error.");
            return 1;
        }
    }
    public static void main(String[] args) {
        if(args.length==0) {
            if(GraphicsEnvironment.isHeadless()){System.err.println("Desktop display unavailable; use --help for the CLI.");System.exit(1);}
            SwingUtilities.invokeLater(()->new Window().setVisible(true));
        } else System.exit(cli(args,System.out,System.err));
    }
}
