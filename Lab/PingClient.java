import java.io.*;
import java.net.*;
import java.util.*;
 
public class PingClient {
    static private final int ping_time = 9;
    static private final int TIMEOUT = 1000;

	public static void main(String[] args) {
        String server = args[0];
        int port = Integer.parseInt(args[1]);
        long t1 = 0, t2 = 0;
        long[] RTTs = new long[10];          // list for storing rtts
        int RTT_succ = 0; 

		SocketAddress local_addr = new InetSocketAddress("localhost", 3231);
		try {
			DatagramSocket sender = new DatagramSocket(local_addr);
            byte[] buf1 = new byte[1024];
            DatagramPacket dp_receive = new DatagramPacket(buf1, 1024);
            sender.setSoTimeout(TIMEOUT);                // set timeout
			int count = -1;

			while(count < ping_time){
				count++;
                long timeStamp = System.currentTimeMillis();
				byte[] buf = ("PING " + count + " " + timeStamp +"\r\n").getBytes();
				SocketAddress receive_addr = new InetSocketAddress(server, port);
				DatagramPacket data = new DatagramPacket(buf, buf.length, receive_addr);
				try {
					sender.send(data);
                    t1 = System.currentTimeMillis();
				} catch (Exception e) {
					e.printStackTrace();
				}
                
                // try to revice response from server.
                while (true) {
                    try {
                        sender.receive(dp_receive);
                        t2 = System.currentTimeMillis();    // already receive message
                        RTTs[RTT_succ] = t2 - t1;
                        RTT_succ ++;
                        System.out.println("ping to "+ server + ", seq = "+ count + ", rtt = " + (t2 - t1) + "ms");
                        break;
                    }
                    catch (InterruptedIOException e){       // Time out
                        System.out.println("ping to "+ server + ", seq = "+ count + ", time out");
                        break;
                    }
                    catch (IOException e1){                 // can not receive any message
                        continue;
                    }
                }
			}
			sender.close();
		} catch (SocketException e) {
			e.printStackTrace();
		}
		
        if (RTT_succ != 0) {                               // not all requests are time out
            long max = RTTs[0], min = RTTs[0], avg = 0;

            for (int i = 0; i < RTT_succ; i ++) {
                if (RTTs[i] > max)
                    max = RTTs[i];
                if (RTTs[i] < min)
                    min = RTTs[i];
                avg += RTTs[i];
            }
            System.out.println("Minimum RTTs:" + min + " Maximum RTTs:" + max + " Average RTTs:" + avg / RTT_succ);
        }
	}
}
