// ConnectionHandler.java
// 2005.06.29.08.11
// 2008.11.04.09.56

import java.io.*;
import java.net.*;


public class ConnectionHandler extends Thread
{
   Socket socket = null;
   BufferedReader readsocket = null;
   PrintStream    writesocket = null;
   ConnectionListener client = null;

   public String  IPAddress = null;
   public boolean logged_in = false;

   ConnectionHandler(Socket s,ConnectionListener c)
   {
      client = c;
      socket = s;
      try {
      readsocket = new BufferedReader( new InputStreamReader( s.getInputStream() ) );
      writesocket = new PrintStream(  s.getOutputStream() ) ;
      }
      catch(Exception e) { System.out.println("ConnectionHandler constructor() " +e); }
      IPAddress = s.getInetAddress().toString();
   }

   public void run()
   {
      try {

      while(socket.isConnected())
      {
         if(readsocket.ready())
         {
            client.dataready( readsocket.readLine(), socket.getInetAddress().toString() );
         }
         Thread.sleep(100);
            
      }

      } /* end try */
      catch(Exception e) { System.out.println("ConnectionHandler run(): "+e); }
   }

   public void sendmessage(String s)
   {
       writesocket.println(s);     
   }

}