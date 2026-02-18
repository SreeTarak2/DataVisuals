"use client"

import * as React from "react"
import { Search, MessageSquare, Trash2, Calendar, ExternalLink } from "lucide-react"
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { DeleteConfirmDialog } from "@/components/ui/delete-confirm-dialog"
import { cn } from "@/lib/utils"
import useChatStore from '../../../store/chatStore';
import useDatasetStore from '../../../store/datasetStore';
import { toast } from 'react-hot-toast';

export default function ChatHistoryModal({ isOpen, onClose }) {
  const [search, setSearch] = React.useState("")
  const [activeId, setActiveId] = React.useState(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false)
  const [chatToDelete, setChatToDelete] = React.useState(null)
  const navigate = useNavigate();

  const { conversations, clearConversation, setCurrentConversation, loadConversations } = useChatStore();
  const { datasets } = useDatasetStore();

  // Load conversations on mount or when opened
  React.useEffect(() => {
    if (isOpen) {
      loadConversations();
    }
  }, [isOpen, loadConversations]);

  // Generate a smart title from the first user message
  const generateTitle = (messages, datasetName) => {
    // Find the first user message
    const firstUserMessage = messages.find(m => m.role === 'user');

    if (firstUserMessage?.content && typeof firstUserMessage.content === 'string') {
      let title = firstUserMessage.content.trim();

      // Remove common prefixes
      title = title.replace(/^(show me|can you|please|i want to|help me|what is|what are|how do|tell me)/i, '').trim();

      // Capitalize first letter
      title = title.charAt(0).toUpperCase() + title.slice(1);

      // Truncate to reasonable length
      if (title.length > 50) {
        title = title.substring(0, 47) + '...';
      }

      return title || datasetName || 'New Chat';
    }

    // Fallback to dataset name or generic title
    return datasetName ? `Chat about ${datasetName}` : 'New Chat';
  };

  // Transform conversations to display format
  const formattedConversations = React.useMemo(() => {
    return Object.values(conversations).map(conv => {
      const dataset = datasets.find(d => d.id === conv.datasetId);
      const messages = conv.messages || [];
      const lastMessage = messages[messages.length - 1];
      const datasetName = conv.datasetName || dataset?.name;

      // Generate smart title from first user message
      const title = generateTitle(messages, datasetName);

      // Determine snippet text from last message
      let snippet = 'No messages';
      if (lastMessage?.content) {
        if (typeof lastMessage.content === 'string') {
          snippet = lastMessage.content.length > 100
            ? lastMessage.content.substring(0, 97) + '...'
            : lastMessage.content;
        } else {
          snippet = 'Chart/Analysis';
        }
      }

      return {
        id: conv.id,
        title: title,
        snippet: snippet,
        datasetName: datasetName || 'Unknown Dataset',
        date: new Date(conv.createdAt || conv.timestamp || Date.now()).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        timestamp: new Date(conv.createdAt || conv.timestamp || Date.now()),
        type: lastMessage?.role === 'user' ? 'user' : 'ai',
        unread: false
      };
    }).sort((a, b) => b.timestamp - a.timestamp);
  }, [conversations, datasets]);

  const filteredConversations = formattedConversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase()) ||
    c.snippet.toLowerCase().includes(search.toLowerCase())
  )

  const handleOpenChat = (chatId) => {
    setCurrentConversation(chatId);
    navigate(`/app/chat?chatId=${chatId}`);
    onClose();
  };

  const handleDelete = (e, chatId, chatTitle) => {
    e.stopPropagation();
    setChatToDelete({ id: chatId, title: chatTitle });
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (chatToDelete) {
      clearConversation(chatToDelete.id);
      toast.success('Conversation deleted');
      setChatToDelete(null);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[calc(100%-2rem)] sm:max-w-2xl border-zinc-800 bg-zinc-950 p-0 text-zinc-100 shadow-2xl">
        <DialogHeader className="p-4 sm:p-6 pb-2 pr-12 sm:pr-14">
          <div className="flex items-center gap-3">
            <DialogTitle className="text-lg sm:text-xl font-bold tracking-tight">Chat History</DialogTitle>
            <Badge variant="secondary" className="bg-zinc-900 text-zinc-400 border-zinc-800 text-[10px] sm:text-xs">
              {formattedConversations.length}
            </Badge>
          </div>
          <div className="relative mt-4">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-500" />
            <Input
              placeholder="Search conversations..."
              className="h-9 sm:h-10 border-zinc-800 bg-zinc-900/50 pl-9 text-sm sm:text-base text-zinc-100 placeholder:text-zinc-500 focus-visible:ring-zinc-700"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </DialogHeader>

        <ScrollArea className="h-[350px] sm:h-[450px] px-2 pb-6">
          <div className="space-y-1 p-2">
            {filteredConversations.length > 0 ? (
              filteredConversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => handleOpenChat(conv.id)}
                  className={cn(
                    "group relative flex cursor-pointer items-start gap-3 sm:gap-4 rounded-xl p-3 sm:p-4 transition-all duration-200",
                    "hover:bg-zinc-900/80 active:scale-[0.98]",
                    activeId === conv.id ? "bg-zinc-900 ring-1 ring-zinc-800" : "bg-transparent"
                  )}
                  onMouseEnter={() => setActiveId(conv.id)}
                  onMouseLeave={() => setActiveId(null)}
                >
                  <Avatar className="mt-0.5 size-8 sm:size-10 shrink-0 border border-zinc-800 shadow-sm">
                    <AvatarImage src={`https://avatar.vercel.sh/${conv.title}`} />
                    <AvatarFallback className="bg-zinc-800 text-zinc-400 text-xs sm:text-sm">
                      {conv.title[0]}
                    </AvatarFallback>
                  </Avatar>

                  <div className="flex-1 space-y-0.5 sm:space-y-1 overflow-hidden">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className={cn(
                        "truncate text-sm sm:text-base font-medium transition-colors",
                        conv.unread ? "text-zinc-100" : "text-zinc-300",
                        activeId === conv.id ? "text-white" : ""
                      )}>
                        {conv.title}
                      </h3>
                      <div className="relative flex items-center gap-2 shrink-0">
                        <span className="text-[10px] sm:text-[11px] font-medium text-zinc-500 transition-opacity group-hover:opacity-0">
                          {conv.date}
                        </span>
                        <div className="absolute right-0 top-1/2 -translate-y-1/2 opacity-0 transition-opacity group-hover:opacity-100">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-6 sm:size-7 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
                            onClick={(e) => handleDelete(e, conv.id, conv.title)}
                          >
                            <Trash2 className="size-3 sm:size-3.5" />
                          </Button>
                        </div>
                      </div>
                    </div>
                    <p className="line-clamp-1 text-xs sm:text-sm text-zinc-500 transition-colors group-hover:text-zinc-400">
                      {conv.snippet}
                    </p>
                  </div>

                  {conv.unread && (
                    <div className="absolute right-3 sm:right-4 top-1/2 size-1.5 sm:size-2 -translate-y-1/2 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]" />
                  )}
                </div>
              ))
            ) : (
              <div className="flex h-32 flex-col items-center justify-center space-y-2 text-center">
                <div className="rounded-full bg-zinc-900 p-3">
                  <Search className="size-6 text-zinc-700" />
                </div>
                <p className="text-sm text-zinc-500">No conversations found</p>
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="border-t border-zinc-800 p-4 bg-zinc-950/50">
          <Button variant="ghost" className="w-full justify-start gap-2 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200" onClick={() => navigate('/app/chat')}>
            <MessageSquare className="size-4" />
            <span className="text-xs font-medium">New Chat</span>
          </Button>
        </div>
      </DialogContent>

      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={confirmDelete}
        title="Delete Conversation"
        description="Are you sure you want to delete this conversation? This action cannot be undone and all messages will be permanently removed."
        itemName={chatToDelete?.title}
      />
    </Dialog>
  )
}