import { useState, useRef } from 'react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    { sender: 'bot', text: 'Hello! I am your CUDA documentation assistant. Ask me anything about CUDA programming.' }
  ]);
  const [input, setInput] = useState('');
  const chatEndRef = useRef(null);

  // Send message to the RAG backend
  const sendMessage = async () => {
    if (!input.trim()) return;
    
    const userMsg = { sender: 'user', text: input };
    setMessages((msgs) => [...msgs, userMsg]);
    const currentInput = input;
    setInput('');
    
    // Add a loading message
    const loadingMsg = { sender: 'bot', text: '🤔 Searching CUDA documentation...', isLoading: true };
    setMessages((msgs) => [...msgs, loadingMsg]);
    
    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: currentInput,
          session_id: null // You can implement session management later if needed
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // Remove loading message and add real response
      setMessages((msgs) => {
        const filteredMsgs = msgs.filter(msg => !msg.isLoading);
        return [...filteredMsgs, { 
          sender: 'bot', 
          text: data.response,
          citations: data.citations || [],
          sessionId: data.session_id,
          interactionId: data.interaction_id
        }];
      });
      
    } catch (error) {
      console.error('Error calling backend:', error);
      
      // Remove loading message and show error
      setMessages((msgs) => {
        const filteredMsgs = msgs.filter(msg => !msg.isLoading);
        return [...filteredMsgs, { 
          sender: 'bot', 
          text: `❌ Sorry, I couldn't connect to the backend. Please make sure the backend server is running on http://localhost:8000. Error: ${error.message}`
        }];
      });
    }
    
    // Scroll to bottom
    setTimeout(() => {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') sendMessage();
  };

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h1>CUDA Documentation Chatbot</h1>
        <p className="chat-subtitle">Ask questions about CUDA C++ Programming Guide</p>
      </header>
      <div
        className="chat-history"
        style={{
          height: '400px',
          overflowY: 'auto',
          background: '#f5f7fa',
          border: '1px solid #ddd',
          borderRadius: '16px',
          padding: '1rem',
          marginBottom: '1rem',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start',
              marginBottom: '0.5rem',
            }}
          >
            <div
              style={{
                maxWidth: '70%',
                padding: '0.75rem 1rem',
                borderRadius: '18px',
                background: msg.sender === 'user' ? '#4f8cff' : '#e5e5ea',
                color: msg.sender === 'user' ? '#fff' : '#222',
                alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                wordBreak: 'break-word',
              }}
            >
              {msg.text}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>
      <div className="chat-input-row" style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your CUDA question..."
          className="chat-input"
          style={{
            flex: 1,
            borderRadius: '20px',
            border: '1px solid #ccc',
            padding: '0.75rem 1rem',
            fontSize: '1rem',
            outline: 'none',
          }}
        />
        <button
          onClick={sendMessage}
          className="send-btn"
          style={{
            borderRadius: '20px',
            background: '#4f8cff',
            color: '#fff',
            border: 'none',
            padding: '0.75rem 1.5rem',
            fontWeight: 'bold',
            fontSize: '1rem',
            cursor: 'pointer',
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default App;
