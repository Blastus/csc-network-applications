// ServerHandler.java
// 2005.06.29.08.40


import java.net.*;


public class ServerHandler extends Thread
{
   ServerSocket ss = null;
   ConnectionListener cl = null;

   ServerHandler(ConnectionListener c)
   {
      try {
      ss  = new ServerSocket(8989);
      cl = c;
      }
      catch(Exception e) { System.out.println("ServerHandler constructor: " +e); }

   }

   public void run()
   {
      ConnectionHandler j = null;
      try {

      while(true)
      {
         System.out.println("ServerHandler run() top");
         j = new ConnectionHandler(ss.accept(),cl);
         System.out.println("ServerHandler run() middle");
         System.out.println("ConnectionListener " + cl + "//" + "ConnectionHandler " + j );
         cl.addAConnection(j);
         System.out.println("ServerHandler run() bottom");
         j.start();
         System.out.println("ServerHandler run() end");
         
      }

      } /* end try */
      catch(Exception e) { 
         System.out.println("ConnectionListener " + cl + "//" + "ConnectionHandler " + j );
System.out.println("ServerHandler run(): "+e); e.printStackTrace(); }

   }


}