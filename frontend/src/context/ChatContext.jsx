/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext } from 'react';
import { AuthContext } from './AuthContext';
import { useChatLogic } from '../hooks/useChatLogic';

const ChatContext = createContext(null);

export const ChatProvider = ({ children }) => {
  const { user } = useContext(AuthContext);
  const chatLogic = useChatLogic(user);

  return (
    <ChatContext.Provider value={chatLogic}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};
