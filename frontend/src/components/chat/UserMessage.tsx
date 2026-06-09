import { User } from "lucide-react";
import type { ChatMessage } from "../../types/chat";

interface Props {
  message: ChatMessage;
}

export default function UserMessage({ message }: Props) {
  return (
    <div className="flex gap-3 py-4">
      {/* 头像 */}
      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
        <User className="w-4 h-4 text-white" />
      </div>

      {/* 消息气泡 */}
      <div className="message-user">
        <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
          {message.content}
        </p>
      </div>
    </div>
  );
}
