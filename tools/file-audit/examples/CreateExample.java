/* Fictional, new-directory-only example generator. MIT. */
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.charset.StandardCharsets;

public final class CreateExample {
    public static void main(String[] args) throws Exception {
        if(args.length!=1) { System.err.println("Supply one new example directory under an existing local parent.");System.exit(1); }
        Path destination=Path.of(args[0]).toAbsolutePath().normalize();
        if(destination.toString().startsWith("\\\\")||Files.exists(destination,LinkOption.NOFOLLOW_LINKS))throw new IllegalArgumentException("New local destination required");
        Path current=destination.getParent().getRoot();
        for(Path part:destination.getParent()) {
            current=current.resolve(part);
            var a=Files.readAttributes(current,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
            if(!a.isDirectory()||a.isSymbolicLink()||a.isOther()||!current.toRealPath(LinkOption.NOFOLLOW_LINKS).equals(current.toRealPath()))throw new IllegalArgumentException("Plain existing parent required");
        }
        Files.createDirectory(destination);
        Files.createDirectory(destination.resolve("notes"));Files.createDirectory(destination.resolve("copies"));
        Files.writeString(destination.resolve("notes/alpha.txt"),"fictional sample\n",StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
        Files.writeString(destination.resolve("copies/alpha-copy.txt"),"fictional sample\n",StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
        Files.writeString(destination.resolve("different.txt"),"different sample\n",StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
        Files.write(destination.resolve("empty.txt"),new byte[0],StandardOpenOption.CREATE_NEW);
        System.out.println("Created four fictional input files in a new directory. Existing directories are never replaced; an I/O error may leave a partial example.");
    }
}
