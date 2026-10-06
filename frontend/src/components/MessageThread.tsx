import React from 'react';

interface MessageThreadProps {
  children: React.ReactNode;
  endRef: React.RefObject<HTMLDivElement | null>;
}

export const MessageThread: React.FC<MessageThreadProps> = ({ children, endRef }) => (
  <div className="flex-1 min-h-0 overflow-y-auto p-6">
    <div className="max-w-[1120px] mx-auto space-y-4">
      {children}
      <div ref={endRef} />
    </div>
  </div>
);
