// MultichatClient.java
// 2005.06.29.08.28
// 2005.06.30.23.32


import java.awt.*;
import java.awt.event.*;
import java.io.*;
import java.net.*;
import java.util.*;

public class MultichatClient extends Frame 
implements ConnectionListener,WindowListener,MouseListener,KeyListener
{
   private TextArea message_area = null;
   private TextField send_area = null;
   ConnectionHandler remote = null;

   MultichatClient(String s,String remote_host)
   {
      super(s);


      this.addWindowListener(this);
      this.setSize(400,200);
      this.setLayout(new BorderLayout() );
      
      message_area = new TextArea();

      this.add(message_area,"Center");

      Panel p = new Panel();

      p.setLayout(new FlowLayout());

      send_area = new TextField(40);
      send_area.addKeyListener(this);
      p.add(send_area );
      Button b = new Button("Send");
      b.addMouseListener(this);
      p.add(b);

      this.add(p,"South");
      
      this.setVisible(true);

      send_area.requestFocus();

      try {
         Socket remote_socket = new Socket(remote_host,8989);
         remote = new ConnectionHandler(remote_socket,this);
         remote.start();   // Don't forget to start your Thread!!
      }
      catch(UnknownHostException e)
      {
         System.out.println("Could not find host " + remote_host + ".");
      }
      catch(IOException e)
      {
         System.out.println("Could not connect to host " + remote_host + ".");
      }
      
   }


   public static void main(String[] args)
   {
      MultichatClient m = new MultichatClient("MultichatClient version 1.0", args[0]);

   }

   public void addAConnection(ConnectionHandler ch)
   {
      
   }

   public void dataready(String s,String address)
   {
         if( !address.endsWith( "172.16.222.192" ) )
            message_area.append(address + "> " + s + "\r\n");
   }

   public void windowActivated(WindowEvent e)
   {
   }

   public void windowDeactivated(WindowEvent e)
   {
   }

   public void windowOpened(WindowEvent e)
   {
   }

   public void windowIconified(WindowEvent e)
   {
   }

   public void windowDeiconified(WindowEvent e)
   {
   }

   public void windowClosing(WindowEvent e)
   {
      this.dispose();
   }

   public void windowClosed(WindowEvent e)
   {
      System.exit(1);
   }

   public void mouseClicked(MouseEvent e)
   {
      remote.sendmessage(send_area.getText());
      message_area.append("local > " + send_area.getText() + "\r\n" );
      
   }

   public void mouseEntered(MouseEvent e)
   {
      
   }

   public void mouseExited(MouseEvent e)
   {
      
   }

   public void mousePressed(MouseEvent e)
   {
      
   }

   public void mouseReleased(MouseEvent e)
   {
      
   }

   public void keyPressed(KeyEvent e)
   {
      if(e.getKeyCode()==10)
      {
         remote.sendmessage(send_area.getText());
         message_area.append("local > " + send_area.getText() + "\r\n" );
      }
   }

   public void keyTyped(KeyEvent e)
   {
   }
   public void keyReleased(KeyEvent e)
   {
   }

}
