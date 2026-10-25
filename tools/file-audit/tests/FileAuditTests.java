/* Original synthetic File Audit tests. MIT. No real user directories are scanned. */
import java.awt.*;
import java.io.*;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.*;
import java.time.Instant;
import java.util.List;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import javax.swing.*;
import javax.swing.table.*;

public final class FileAuditTests {
    static int passed, skipped;
    interface Test { void run() throws Exception; }
    static final class Skip extends Exception {
        private static final long serialVersionUID = 1L;
        Skip(String reason) { super(reason); }
    }
    static void run(String name, Test test) throws Exception {
        try { test.run(); passed++; System.out.println("PASS " + name); }
        catch (Skip e) { skipped++; System.out.println("SKIP " + name + " (" + e.getMessage() + ")"); }
    }
    static void check(boolean value) { if (!value) throw new AssertionError("Expected condition not met"); }
    static void rejects(Test test) throws Exception {
        boolean rejected=false;
        try { test.run(); } catch (IOException | IllegalArgumentException e) { rejected=true; }
        check(rejected);
    }
    static final class Fixture implements AutoCloseable {
        final Path root, base;
        Fixture() throws IOException {
            base=Path.of(System.getProperty("java.io.tmpdir")).toRealPath();
            root=Files.createTempDirectory(base,"file-audit-test-").toAbsolutePath().normalize();
            check(root.startsWith(base)&&!root.equals(base));
        }
        Path file(String name,String text) throws IOException {
            Path p=root.resolve(name);Files.createDirectories(p.getParent());Files.writeString(p,text,StandardCharsets.UTF_8);return p;
        }
        private void clean(Path p) throws IOException {
            Path normalized=p.toAbsolutePath().normalize();
            if(!normalized.startsWith(root)||normalized.equals(base))throw new IOException("test_cleanup_scope");
            BasicFileAttributes a=Files.readAttributes(p,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
            boolean link=a.isSymbolicLink()||a.isOther()||!p.toRealPath(LinkOption.NOFOLLOW_LINKS).equals(p.toRealPath());
            if(a.isDirectory()&&!link)try(DirectoryStream<Path> entries=Files.newDirectoryStream(p)){for(Path child:entries)clean(child);}
            Files.delete(p);
        }
        public void close() throws IOException { clean(root); }
    }
    static FileAudit.Config cfg(Path p) { return new FileAudit.Config(p,true,Set.of(),100,200,4*FileAudit.MIB,8*FileAudit.MIB,8,60000); }
    static FileAudit.Config limits(Path p,boolean hashes,int files,int entries,long perFile,long total,int depth,long millis) {
        return new FileAudit.Config(p,hashes,Set.of(),files,entries,perFile,total,depth,millis);
    }
    static FileAudit.Report scan(Path p) throws IOException { return FileAudit.scan(cfg(p),new AtomicBoolean(),x->{}); }
    static boolean issue(FileAudit.Report r,String code) { return r.issues.stream().anyMatch(x->x.code().equals(code)); }
    static void symlink(Path link,Path target) throws Skip {
        try { Files.createSymbolicLink(link,target); }
        catch(IOException | UnsupportedOperationException | SecurityException e) { throw new Skip("native symbolic-link creation unavailable"); }
    }
    static void junction(Path link,Path target) throws Exception {
        if(!System.getProperty("os.name").startsWith("Windows"))throw new Skip("Windows-only junction fixture");
        // Only generated fixture paths with a conservative shell-safe alphabet.
        if(!link.toString().matches("[A-Za-z0-9_:\\\\ .-]+")||!target.toString().matches("[A-Za-z0-9_:\\\\ .-]+"))throw new Skip("fixture path not suitable for native junction setup");
        Process p=new ProcessBuilder("cmd.exe","/d","/c","mklink","/J",link.toString(),target.toString()).redirectErrorStream(true).start();
        p.getInputStream().readAllBytes();
        if(!p.waitFor(10,TimeUnit.SECONDS)){p.destroyForcibly();throw new Skip("junction setup timeout");}
        if(p.exitValue()!=0)throw new Skip("native junction creation unavailable");
    }
    static int cli(String[] args,ByteArrayOutputStream output,ByteArrayOutputStream error) {
        return FileAudit.cli(args,new PrintStream(output,true,StandardCharsets.UTF_8),new PrintStream(error,true,StandardCharsets.UTF_8));
    }

    public static void main(String[] args) throws Exception {
        run("SHA-256 matches the published abc test vector",()->{
            try(Fixture f=new Fixture()){f.file("a.txt","abc");var r=scan(f.root);check(r.status.equals("complete"));check(r.files.get(0).sha256().equals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"));}
        });
        run("duplicates require equal length and SHA-256; empty files excluded",()->{
            try(Fixture f=new Fixture()){f.file("a.txt","same");f.file("sub/b.txt","same");f.file("other.txt","diff");f.file("e1","");f.file("e2","");var r=scan(f.root);check(r.files.size()==5&&r.groups.size()==1);check(r.groups.get(0).paths().size()==2);check(r.totalFileBytes.equals(BigInteger.valueOf(12)));}
        });
        run("file contents and modification times are not changed",()->{
            try(Fixture f=new Fixture()){Path p=f.file("original.bin","keep unchanged");byte[] before=Files.readAllBytes(p);var time=Files.getLastModifiedTime(p);scan(f.root);check(Arrays.equals(before,Files.readAllBytes(p)));check(time.equals(Files.getLastModifiedTime(p)));try(var list=Files.list(f.root)){check(list.count()==1);}}
        });
        run("metadata-only never invokes the content-read hook",()->{
            try(Fixture f=new Fixture()){f.file("a.txt","larger than limits");var r=FileAudit.scan(limits(f.root,false,10,20,1,1,8,60000),new AtomicBoolean(),x->{},p->{throw new AssertionError("must not read");});check(r.status.equals("complete")&&r.bytesRead==0&&r.groups.isEmpty());check(r.files.get(0).sha256()==null);}
        });
        run("extension filter is case-insensitive and explicit",()->{
            try(Fixture f=new Fixture()){f.file("a.TXT","a");f.file("b.json","b");f.file("c.dat","c");var c=new FileAudit.Config(f.root,true,FileAudit.parseExtensions(".TXT, .json"),10,20,100,100,8,60000);var r=FileAudit.scan(c,new AtomicBoolean(),x->{});check(r.files.size()==2);check(r.files.stream().noneMatch(x->x.path().endsWith("dat")));}
        });
        run("invalid filter syntax and wildcards are rejected",()->{
            for(String s:List.of("*","txt",".txt,",".txt/.json"))rejects(()->FileAudit.parseExtensions(s));
        });
        run("file count is bounded and partial",()->{
            try(Fixture f=new Fixture()){f.file("a","a");f.file("b","b");var r=FileAudit.scan(limits(f.root,true,1,20,100,100,8,60000),new AtomicBoolean(),x->{});check(r.files.size()==1&&issue(r,"file_limit")&&r.status.equals("partial"));}
        });
        run("entry count also bounds empty-directory discovery",()->{
            try(Fixture f=new Fixture()){Files.createDirectory(f.root.resolve("child"));var r=FileAudit.scan(limits(f.root,true,10,1,100,100,8,60000),new AtomicBoolean(),x->{});check(r.entries==1&&issue(r,"entry_limit"));}
        });
        run("depth limit is reported instead of silently omitting subtrees",()->{
            try(Fixture f=new Fixture()){f.file("root.txt","x");f.file("deep/a.txt","y");var r=FileAudit.scan(limits(f.root,true,10,20,100,100,1,60000),new AtomicBoolean(),x->{});check(r.files.size()==1&&issue(r,"depth_limit"));}
        });
        run("per-file hash limit retains inventory metadata",()->{
            try(Fixture f=new Fixture()){f.file("large.bin","12345");var r=FileAudit.scan(limits(f.root,true,10,20,1,100,8,60000),new AtomicBoolean(),x->{});check(r.files.size()==1&&r.files.get(0).bytes()==5&&r.bytesRead==0);check(issue(r,"file_size_limit")&&r.files.get(0).sha256()==null);}
        });
        run("total hash-byte budget is not exceeded",()->{
            try(Fixture f=new Fixture()){f.file("a","x");f.file("b","x");f.file("c","x");var r=FileAudit.scan(limits(f.root,true,10,20,100,2,8,60000),new AtomicBoolean(),x->{});check(r.bytesRead==2&&r.files.size()==3&&issue(r,"hash_byte_limit"));}
        });
        run("pre-cancel returns a cancelled partial inventory",()->{
            try(Fixture f=new Fixture()){f.file("a","x");var r=FileAudit.scan(cfg(f.root),new AtomicBoolean(true),x->{});check(r.status.equals("cancelled")&&r.files.isEmpty());}
        });
        run("cancellation before content read discards an unfinished digest",()->{
            try(Fixture f=new Fixture()){f.file("a","abcdef");AtomicBoolean stop=new AtomicBoolean();var r=FileAudit.scan(cfg(f.root),stop,x->{},p->stop.set(true));check(r.status.equals("cancelled")&&r.bytesRead==0&&r.files.get(0).sha256()==null);}
        });
        run("cooperative time budget produces a partial result",()->{
            try(Fixture f=new Fixture()){f.file("a","abcdef");var r=FileAudit.scan(limits(f.root,true,10,20,100,100,8,1),new AtomicBoolean(),x->{},p->{try{Thread.sleep(10);}catch(InterruptedException e){Thread.currentThread().interrupt();}});check(issue(r,"time_limit")&&r.status.equals("partial"));}
        });
        run("size mutation invalidates the checksum",()->{
            try(Fixture f=new Fixture()){f.file("a","abc");var r=FileAudit.scan(cfg(f.root),new AtomicBoolean(),x->{},p->{try{Files.writeString(p,"longer content");}catch(IOException e){throw new UncheckedIOException(e);}});check(r.files.get(0).sha256()==null&&issue(r,"changed_or_unreadable"));}
        });
        run("same-size mutation with changed metadata invalidates checksum",()->{
            try(Fixture f=new Fixture()){f.file("a","abc");var r=FileAudit.scan(cfg(f.root),new AtomicBoolean(),x->{},p->{try{var old=Files.getLastModifiedTime(p);Files.writeString(p,"xyz");Files.setLastModifiedTime(p,FileTime.fromMillis(old.toMillis()+5000));}catch(IOException e){throw new UncheckedIOException(e);}});check(r.files.get(0).sha256()==null&&issue(r,"changed_or_unreadable"));}
        });
        run("disappearing file produces a bounded path-free error code",()->{
            try(Fixture f=new Fixture()){f.file("a","abc");var r=FileAudit.scan(cfg(f.root),new AtomicBoolean(),x->{},p->{try{Files.delete(p);}catch(IOException e){throw new UncheckedIOException(e);}});check(issue(r,"changed_or_unreadable"));check(!FileAudit.json(r.data()).contains(f.root.toString()));}
        });
        run("native symbolic file links are not read",()->{
            try(Fixture f=new Fixture();Fixture outside=new Fixture()){Path target=outside.file("private.txt","not read");symlink(f.root.resolve("alias"),target);var r=scan(f.root);check(r.files.isEmpty()&&r.bytesRead==0&&issue(r,"linked_or_special_file"));}
        });
        run("linked roots are rejected",()->{
            try(Fixture f=new Fixture();Fixture outside=new Fixture()){symlink(f.root.resolve("alias"),outside.root);rejects(()->scan(f.root.resolve("alias")));}
        });
        run("existing Windows junctions are not traversed",()->{
            try(Fixture f=new Fixture();Fixture outside=new Fixture()){outside.file("private.txt","not read");junction(f.root.resolve("alias"),outside.root);var r=scan(f.root);check(r.files.isEmpty()&&r.bytesRead==0);check(r.issueCount>0);}
        });
        run("hard-link aliases do not become separate duplicate candidates",()->{
            try(Fixture f=new Fixture()){Path a=f.file("a","content");try{Files.createLink(f.root.resolve("alias"),a);}catch(IOException|UnsupportedOperationException e){throw new Skip("hard-link creation unavailable");}var r=scan(f.root);if(r.files.stream().anyMatch(x->x.identity()==null))throw new Skip("provider file identity unavailable");check(r.groups.isEmpty()&&r.hardLinkAliases==1);}
        });
        run("two separate copies remain candidates with one hard-link alias",()->{
            try(Fixture f=new Fixture()){Path a=f.file("a","content");f.file("b","content");try{Files.createLink(f.root.resolve("alias"),a);}catch(IOException|UnsupportedOperationException e){throw new Skip("hard-link creation unavailable");}var r=scan(f.root);if(r.files.stream().anyMatch(x->x.identity()==null))throw new Skip("provider file identity unavailable");check(r.groups.size()==1&&r.groups.get(0).paths().size()==2&&r.hardLinkAliases==1);}
        });
        run("Unicode and spaces survive relative path reporting",()->{
            try(Fixture f=new Fixture()){f.file("sub space/café-🎮.txt","content");var r=scan(f.root);check(r.files.get(0).path().equals("sub space/café-🎮.txt"));check(!FileAudit.json(r.data()).contains(f.root.toString()));}
        });
        run("placeholder cheat filenames have no security verdict",()->{
            try(Fixture f=new Fixture()){f.file("cheat.dll","");f.file("injector.exe","");var r=scan(f.root);check(r.status.equals("complete")&&r.groups.isEmpty());check(r.files.stream().allMatch(x->x.hashStatus().equals("hashed")));}
        });
        run("JSON escapes control characters and quotes",()->{
            check(FileAudit.json("a\"b\\c\n\t").equals("\"a\\\"b\\\\c\\u000a\\u0009\""));
            check(FileAudit.json("🎮").equals("\"\\ud83c\\udfae\""));
            check(FileAudit.json(new BigInteger("99999999999999999999")).equals("99999999999999999999"));
        });
        run("issue details are bounded but omitted count remains visible",()->{
            var r=FileAudit.demo();for(int i=0;i<1010;i++)r.issue("example","synthetic");check(r.issues.size()==1000&&r.issueCount==1010);check(FileAudit.json(r.data()).contains("\"issues_omitted\":10"));
        });
        run("new report is created outside the scanned input",()->{
            try(Fixture f=new Fixture()){Path root=Files.createDirectory(f.root.resolve("input"));Files.writeString(root.resolve("a"),"abc");var r=scan(root);Path out=f.root.resolve("report.json");FileAudit.save(out,r);check(Files.readString(out).contains("outlands-file-audit/1"));}
        });
        run("existing report is never overwritten",()->{
            try(Fixture f=new Fixture()){Path out=f.file("report.json","keep");rejects(()->FileAudit.save(out,FileAudit.demo()));check(Files.readString(out).equals("keep"));}
        });
        run("report output inside input is rejected",()->{
            try(Fixture f=new Fixture()){var r=scan(f.root);rejects(()->FileAudit.save(f.root.resolve("report.json"),r));check(!Files.exists(f.root.resolve("report.json")));}
        });
        run("report extension and missing output parent are rejected",()->{
            try(Fixture f=new Fixture()){rejects(()->FileAudit.save(f.root.resolve("report.txt"),FileAudit.demo()));rejects(()->FileAudit.save(f.root.resolve("absent/report.json"),FileAudit.demo()));}
        });
        run("linked output parent is rejected",()->{
            try(Fixture f=new Fixture();Fixture outside=new Fixture()){symlink(f.root.resolve("alias"),outside.root);rejects(()->FileAudit.save(f.root.resolve("alias/report.json"),FileAudit.demo()));check(!Files.exists(outside.root.resolve("report.json")));}
        });
        run("invalid scan limits and extension sets are rejected",()->{
            try(Fixture f=new Fixture()){rejects(()->limits(f.root,true,0,20,100,100,8,1000));rejects(()->limits(f.root,true,1,0,100,100,8,1000));rejects(()->limits(f.root,true,1,20,0,100,8,1000));rejects(()->limits(f.root,true,1,20,100,100,0,1000));rejects(()->limits(f.root,true,1,20,100,100,8,0));}
        });
        run("missing and file roots are rejected",()->{
            try(Fixture f=new Fixture()){Path p=f.file("file","x");rejects(()->scan(p));rejects(()->scan(f.root.resolve("absent")));}
        });
        run("CLI demo has no root and is explicitly simulated",()->{
            var out=new ByteArrayOutputStream();var err=new ByteArrayOutputStream();check(cli(new String[]{"--demo"},out,err)==0);check(out.toString(StandardCharsets.UTF_8).contains("\"simulated\":true"));check(err.size()==0);
        });
        run("CLI actual fixture returns a relative-path inventory",()->{
            try(Fixture f=new Fixture()){f.file("one","abc");var out=new ByteArrayOutputStream();var err=new ByteArrayOutputStream();check(cli(new String[]{"--root",f.root.toString()},out,err)==0);check(out.toString(StandardCharsets.UTF_8).contains("\"simulated\":false"));check(!out.toString(StandardCharsets.UTF_8).contains(f.root.toString()));}
        });
        run("CLI partial result exits 2",()->{
            try(Fixture f=new Fixture()){f.file("one","a");f.file("two","b");check(cli(new String[]{"--root",f.root.toString(),"--max-files","1"},new ByteArrayOutputStream(),new ByteArrayOutputStream())==2);}
        });
        run("CLI malformed arguments fail without echoing private values",()->{
            for(String[] values:List.of(new String[]{"--root"},new String[]{"--unknown","private-example"},new String[]{"--demo","--root","private-example"},new String[]{"--root","private-example","--seconds","NaN"},new String[]{"--root","private-example","--max-file-mib","9223372036854775807"})){
                var out=new ByteArrayOutputStream();var err=new ByteArrayOutputStream();check(cli(values,out,err)==1);check(!err.toString(StandardCharsets.UTF_8).contains("private-example"));check(out.size()==0);
            }
        });
        run("CLI existing output is rejected before scan",()->{
            try(Fixture f=new Fixture()){Path output=f.file("report.json","keep");var out=new ByteArrayOutputStream();check(cli(new String[]{"--root",f.root.resolve("absent").toString(),"--output",output.toString()},out,new ByteArrayOutputStream())==1);check(Files.readString(output).equals("keep")&&out.size()==0);}
        });
        run("CLI help opens no folder and needs no GUI",()->{
            var out=new ByteArrayOutputStream();check(cli(new String[]{"--help"},out,new ByteArrayOutputStream())==0);check(out.toString(StandardCharsets.UTF_8).contains("No arguments: desktop app"));
        });
        run("demo group uses the same duplicate classifier as scans",()->{
            var r=FileAudit.demo();check(r.simulated&&r.groups.size()==1&&r.groups.get(0).bytesPerFile()==17&&r.files.size()==3);check(!FileAudit.json(r.data()).contains("fictional-a"));
        });
        if(Arrays.asList(args).contains("--gui")) {
            if(GraphicsEnvironment.isHeadless())throw new AssertionError("GUI tests explicitly requested but no display is available");
            run("GUI starts idle and displays demo candidates",()->SwingUtilities.invokeAndWait(()->{
                var w=new FileAudit.Window();try{check(!w.busy&&w.report==null&&!w.stop.isEnabled());w.demo.doClick();check(w.report.simulated&&w.files.getRowCount()==3&&w.duplicates.getRowCount()==1&&w.export.isEnabled());}finally{w.dispose();}
            }));
            run("GUI filters affect displayed rows only",()->SwingUtilities.invokeAndWait(()->{
                var w=new FileAudit.Window();try{w.display(FileAudit.demo());w.search.setText("copy");check(w.fileTable.getRowCount()==1&&w.report.files.size()==3);}finally{w.dispose();}
            }));
            run("GUI never interprets file labels as HTML",()->SwingUtilities.invokeAndWait(()->{
                var w=new FileAudit.Window();try{TableCellRenderer renderer=w.fileTable.getDefaultRenderer(Object.class);Component c=renderer.getTableCellRendererComponent(w.fileTable,"<html><img src='https://example.invalid/a'>",false,false,0,0);check(c instanceof JLabel&&Boolean.TRUE.equals(((JLabel)c).getClientProperty("html.disable")));check(((JLabel)c).getClientProperty("html")==null);}finally{w.dispose();}
            }));
            run("GUI cancellation waits for the worker result",()->{
                AtomicReference<FileAudit.Window> window=new AtomicReference<>();CountDownLatch entered=new CountDownLatch(1);
                try(Fixture f=new Fixture()){
                    SwingUtilities.invokeAndWait(()->{
                        var w=new FileAudit.Window((config,cancel,progress)->{entered.countDown();while(!cancel.get())try{Thread.sleep(5);}catch(InterruptedException e){break;}var r=new FileAudit.Report(config);r.status="cancelled";r.ended=Instant.now().toString();return r;});window.set(w);w.root.setText(f.root.toString());w.start.doClick();check(w.busy&&!w.start.isEnabled());
                    });
                    check(entered.await(2,TimeUnit.SECONDS));SwingUtilities.invokeAndWait(()->window.get().stop.doClick());
                    long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(3);
                    while(window.get().busy&&System.nanoTime()<until){SwingUtilities.invokeAndWait(()->{});Thread.sleep(10);}
                    SwingUtilities.invokeAndWait(()->{var w=window.get();check(!w.busy&&w.report.status.equals("cancelled")&&w.start.isEnabled());});
                }finally{if(window.get()!=null)SwingUtilities.invokeAndWait(()->window.get().dispose());}
            });
        }
        System.out.println("RESULT passed="+passed+" skipped="+skipped);
    }
}
