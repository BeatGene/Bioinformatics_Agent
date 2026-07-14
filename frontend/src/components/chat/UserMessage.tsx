import { User } from "lucide-react";
import type { ChatMessage } from "../../types/chat";

interface Props {
  message: ChatMessage;
}

export default function UserMessage({ message }: Props) {
  return (
    <div className="flex gap-3 py-5">
      {/* 头像 */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-700 text-white">
        <User className="h-4 w-4" aria-hidden="true" />
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
