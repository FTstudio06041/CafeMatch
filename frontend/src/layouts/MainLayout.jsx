import React from 'react';
import Sidebar from '../components/Sidebar';
import Navbar from '../components/Navbar';

export default function MainLayout({ children }) {
  return (
    <div style={{ display: 'flex', height: '100dvh', overflow: 'hidden', width: '100%' }}>
      <Sidebar />
      <main className="main-container">
        <nav className="navbar">
          <Navbar />
        </nav>
        {children}
      </main>
    </div>
  );
}
