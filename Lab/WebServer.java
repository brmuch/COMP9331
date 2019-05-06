public class SocketHttpServer implements Runnable {

    private final static int PORT = 9999;
    private ServerSocket server = null;

    public static void main(String[] args) {
        new SocketHttpServer();
    }

    public SocketHttpServer() {
        try {
            server = new ServerSocket(PORT);
            if (server == null)
                System.exit(1);
            new Thread(this).start();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    @Override
    public void run() {
        while (true) {
            try {
                Socket client = null;
                client = server.accept();
                if (client != null) {
                    try {
                        System.out.println("Succeed！！...");

                        BufferedReader reader = new BufferedReader(
                                new InputStreamReader(client.getInputStream()));

                        // GET /test.jpg /HTTP1.1
                        String line = reader.readLine();

                        System.out.println("line: " + line);

                        String resource = line.substring(line.indexOf('/'),
                                line.lastIndexOf('/') - 5);

                        System.out.println("the resource you request is: "
                                + resource);

                        resource = URLDecoder.decode(resource, "UTF-8");

                        String method = new StringTokenizer(line).nextElement()
                                .toString();

                        System.out.println("the request method you send is: "
                                + method);

                        while ((line = reader.readLine()) != null) {
                            if (line.equals("")) {
                                break;
                            }
                            System.out.println("the Http Header is : " + line);
                        }

                        if ("post".equals(method.toLowerCase())) {
                            System.out.println("the post request body is: "
                                    + reader.readLine());
                        }

                        if (resource.endsWith(".mkv")) {

                            transferFileHandle("videos/test.mkv", client);
                            closeSocket(client);
                            continue;

                        } else if (resource.endsWith(".jpg")) {

                            transferFileHandle("images/test.jpg", client);
                            closeSocket(client);
                            continue;

                        } else if (resource.endsWith(".rmvb")) {

                            transferFileHandle("videos/test.rmvb", client);
                            closeSocket(client);
                            continue;

                        } else {
                            PrintStream writer = new PrintStream(
                                    client.getOutputStream(), true);
                            writer.println("HTTP/1.0 404 Not found");
                            writer.println();
                            writer.close();
                            closeSocket(client);
                            continue;
                        }
                    } catch (Exception e) {
                        System.out.println("HTTP Server Error:"
                                + e.getLocalizedMessage());
                    }
                }
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    private void closeSocket(Socket socket) {
        try {
            socket.close();
        } catch (IOException ex) {
            ex.printStackTrace();
        }
        System.out.println(socket + "leave");
    }

    private void transferFileHandle(String path, Socket client) {

        File fileToSend = new File(path);

        if (fileToSend.exists() && !fileToSend.isDirectory()) {
            try {
                PrintStream writer = new PrintStream(client.getOutputStream());
                writer.println("HTTP/1.0 200 OK");
                writer.println("Content-Type:application/binary");
                writer.println("Content-Length:" + fileToSend.length());
                writer.println();

                FileInputStream fis = new FileInputStream(fileToSend);
                byte[] buf = new byte[fis.available()];
                fis.read(buf);
                writer.write(buf);
                writer.close();
                fis.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }
}