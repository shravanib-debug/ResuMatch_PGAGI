import './globals.css';

export const metadata = {
  title: 'ResuMatch — AI-Powered Interview System',
  description: 'Dynamic AI interview system using Hybrid Agentic RAG to generate personalised technical questions based on your resume.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
