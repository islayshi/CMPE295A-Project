import { useState } from 'react';
import { MessageSquare, X, Send, User, Bot } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function ChatDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      content: 'I see you are in Hayward with an active fire warning 5 miles away. How can I help you prepare?'
    }
  ]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;
    
    setMessages(prev => [...prev, { role: 'user', content: input }]);
    
    const text = input.trim().toLowerCase();
    
    if (text === "where should i go?") {
      setTimeout(() => {
        setMessages(prev => [...prev, {
          role: 'bot',
          content: 'Based on the active NWS Red Flag Warning and your predicted fire intersection, you should follow the blue route to the Chabot College Evacuation Center. The current AQI outside is 150 (Unhealthy), so keep your windows rolled up. <span class="inline-block text-xs bg-blue-900 px-1.5 py-0.5 rounded cursor-pointer hover:bg-blue-800 ml-1">[NWS]</span> <span class="inline-block text-xs bg-blue-900 px-1.5 py-0.5 rounded cursor-pointer hover:bg-blue-800 ml-1">[CalOES]</span>'
        }]);
      }, 1000);
    } else {
      setTimeout(() => {
        setMessages(prev => [...prev, {
          role: 'bot',
          content: 'This is a prototype. Try asking: "Where should I go?"'
        }]);
      }, 1000);
    }
    setInput('');
  };

  return (
    <>
      <button 
        onClick={() => setIsOpen(true)}
        className={`absolute bottom-6 right-6 p-4 bg-blue-600 hover:bg-blue-500 text-white rounded-full shadow-lg transition-transform z-40 ${isOpen ? 'scale-0' : 'scale-100'}`}
      >
        <MessageSquare size={24} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="absolute top-0 right-0 w-[350px] h-full bg-slate-900/90 backdrop-blur-xl border-l border-slate-700 shadow-2xl flex flex-col z-50 pointer-events-auto"
          >
            <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800/50">
              <h2 className="font-bold text-lg flex items-center gap-2"><Bot size={20}/> RAG Assistant</h2>
              <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${msg.role === 'user' ? 'bg-blue-600' : 'bg-slate-700'}`}>
                    {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                  </div>
                  <div 
                    className={`p-3 rounded-lg max-w-[80%] text-sm ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-800 border border-slate-700 text-slate-200'}`}
                    dangerouslySetInnerHTML={{ __html: msg.content }}
                  />
                </div>
              ))}
            </div>

            <div className="p-4 border-t border-slate-700 bg-slate-800/50">
              <div className="flex gap-2">
                <input 
                  type="text" 
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSend()}
                  placeholder="Ask a safety question..."
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 text-white"
                />
                <button 
                  onClick={handleSend}
                  className="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
                >
                  <Send size={18} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
