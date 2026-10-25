# Source and license scope

Outlands File Audit is original, assistant-assisted application code for
Connor O'Shea / TheOutlandsDev, authorized for MIT publication. It replaces the
design of an unpublished locally authored Java scanner with explicit folder
selection, SHA-256 inventories, candidate grouping, scan limits and a Swing UI.
The prototype's MD5 placeholder signatures, cheat/filename verdicts, fixed system
directories and Gson dependency are omitted. The original private prototype
remains unchanged and is not presented as the tested public application.

The application, fictional generator/report, tests and documentation use the
included [MIT license](LICENSE). The code uses Java SE APIs without copying JDK,
Swing, Gson, malware/signature databases, third-party application implementations
or inspected file data. Java API documentation was consulted for filesystem and
event-thread behavior; no tutorial implementation is bundled.

A JDK 17+ is installed separately and keeps its chosen provider's license. No
JDK/JRE, compiler, class file, native library, executable or installer is shipped.
The MIT grant applies to this original source, not to Java, the operating system
or files inspected by a user. Example inputs and reports are fictional, not an
ownership or safety certification for real data.

Relevant primary API references:

- [Files](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/nio/file/Files.html)
- [SecureDirectoryStream and its platform requirements](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/nio/file/SecureDirectoryStream.html)
- [Swing event and worker threads](https://docs.oracle.com/javase/tutorial/uiswing/concurrency/index.html)

This application performs best-effort path/change checks; it does not claim the
atomic security guarantees of a native descriptor-relative implementation.
Private preservation receipts, original machine paths, user datasets and actual
scan outputs are outside the public release.
