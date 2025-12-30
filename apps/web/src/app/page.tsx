/**
 * Home Page - Main entry point for the DAW application.
 *
 * This page displays the ChatInterface component as the primary
 * user interaction point for the Planner agent.
 */

import ChatInterface from '../components/ChatInterface';

export default function Home() {
  return (
    <main className="h-screen">
      <ChatInterface />
    </main>
  );
}
