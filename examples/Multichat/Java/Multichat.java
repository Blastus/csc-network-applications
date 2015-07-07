// Multichat.java
// 2005.06.29.08.28
// 2005.06.30.23.24
// 2008.11.04.09.56

import java.awt.*;
import java.awt.event.*;
import java.io.*;
import java.net.*;
import java.util.*;

public class Multichat extends Frame 
implements ConnectionListener,WindowListener,MouseListener,KeyListener
{
   private TextArea message_area = null;
   private TextField send_area = null;
   private ServerHandler sh = null;
   private Vector connections = null;
   private int connection_count = 0;

   Multichat(String s)
   {
      super(s);

      connections=new Vector();
      
      sh = new ServerHandler(this);
      sh.start();

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
      
   }


   public static void main(String[] args)
   {
      Multichat m = new Multichat("Multichat version 1.0");

   }

   public void addAConnection(ConnectionHandler ch)
   {
      connections.add(connection_count++,ch);
   }

   public void dataready(String s,String address)
   {

      message_area.append(address + "> " + s + "\r\n");


      Enumeration list = connections.elements();
      while(list.hasMoreElements())
      {
         ConnectionHandler c = (ConnectionHandler)list.nextElement();

         if( !c.logged_in )
         {
            if( s.startsWith( "AUTH" ) && s.endsWith( ":password" ) )
               c.logged_in = true;
         }

         if( c.logged_in )
            c.sendmessage(address + ">" + s);
      }
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
      Enumeration list = connections.elements();
      while(list.hasMoreElements())
      {
         ConnectionHandler c = (ConnectionHandler)list.nextElement();
         c.sendmessage(send_area.getText());
      }
      message_area.append("local > " + send_area.getText() + "\r\n" );
      send_area.setSelectionStart(0);
      send_area.setSelectionEnd( send_area.getText().length() );
      send_area.requestFocus();
      
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
         Enumeration list = connections.elements();
         while(list.hasMoreElements())
         {
            ConnectionHandler c = (ConnectionHandler)list.nextElement();
            c.sendmessage(send_area.getText());
         }
         message_area.append("local > " + send_area.getText() + "\r\n" );
         send_area.setSelectionStart(0);
         send_area.setSelectionEnd( send_area.getText().length() );
      }
   }

   public void keyTyped(KeyEvent e)
   {
   }
   public void keyReleased(KeyEvent e)
   {
   }

}