import type { Metadata } from 'next';
import { DM_Serif_Display, DM_Sans, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const dmSerif = DM_Serif_Display({ subsets: ['latin'], weight: '400', variable: '--font-display', style: ['normal', 'italic'] });
const dmSans = DM_Sans({ subsets: ['latin'], variable: '--font-body' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });

export const metadata: Metadata = {
  title: 'CreatorForge OS — The Agentic Operating System for Creators',
  description: 'A multi-agent operating system that runs the operational spine of a creator business — 12 agents, 8 platforms, autonomous execution.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${dmSerif.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
