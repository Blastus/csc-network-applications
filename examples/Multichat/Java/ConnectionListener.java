// ConnectionListener.java
// 2005.06.29.08.28

public interface ConnectionListener
{
   public void dataready(String data,String sender_name);
   public void addAConnection(ConnectionHandler ch);

}