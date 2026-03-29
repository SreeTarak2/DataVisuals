import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { Settings, CreditCard, FileText, LogOut, User } from "lucide-react";
import { Link } from "react-router-dom";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const Gemini = (props) => (
    <svg
        height="1em"
        style={{
            flex: "none",
            lineHeight: 1,
        }}
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
        width="1em"
        {...props}
    >
        <title>{"Gemini"}</title>
        <defs>
            <linearGradient
                id="lobe-icons-gemini-fill"
                x1="0%"
                x2="68.73%"
                y1="100%"
                y2="30.395%"
            >
                <stop offset="0%" stopColor="#1C7DFF" />
                <stop offset="52.021%" stopColor="#1C69FF" />
                <stop offset="100%" stopColor="#F0DCD6" />
            </linearGradient>
        </defs>
        <path
            d="M12 24A14.304 14.304 0 000 12 14.304 14.304 0 0012 0a14.305 14.305 0 0012 12 14.305 14.305 0 00-12 12"
            fill="url(#lobe-icons-gemini-fill)"
            fillRule="nonzero"
        />
    </svg>
);

export function ProfileDropdown({
    data,
    className,
    expanded = true,
    onLogout,
    ...props
}) {
    const [isOpen, setIsOpen] = useState(false);

    const menuItems = [
        {
            label: "Profile",
            href: "/app/settings/",
            icon: <User className="w-4 h-4" />,
        },
        {
            label: "Model",
            value: data.model,
            href: "/app/settings/",
            icon: <Gemini className="w-4 h-4" />,
        },
        // {
        //     label: "Subscription",
        //     value: data.subscription,
        //     href: "/app/settings/billing",
        //     icon: <CreditCard className="w-4 h-4" />,
        // },
        {
            label: "Settings",
            href: "/app/settings",
            icon: <Settings className="w-4 h-4" />,
        },
        // {
        //     label: "Terms & Policies",
        //     href: "/app/legal",
        //     icon: <FileText className="w-4 h-4" />,
        //     external: true,
        // },
    ];

    return (
        <div className={cn("relative", className)} {...props}>
            <DropdownMenu onOpenChange={setIsOpen}>
                <div className="group relative">
                    <DropdownMenuTrigger asChild>
                        <button
                            type="button"
                            className={cn(
                                "flex items-center gap-3 rounded-2xl bg-surface border border-border hover:border-border-strong hover:bg-elevated transition-all duration-300 focus:outline-none cursor-pointer overflow-hidden",
                                expanded ? "p-2 w-full" : "w-11 h-11 justify-center"
                            )}
                        >
                            <div className="relative shrink-0">
                                <div className={cn(
                                    "rounded-full bg-gradient-to-br from-purple-500 via-pink-500 to-orange-400 p-0.5 shadow-md transition-all duration-300",
                                    expanded ? "w-10 h-10" : "w-9 h-9"
                                )}>
                                    <div className="w-full h-full rounded-full overflow-hidden bg-primary">
                                        <img
                                            src={data.avatar}
                                            alt={data.name}
                                            className="w-full h-full object-cover rounded-full"
                                        />
                                    </div>
                                </div>
                            </div>
                            {expanded && (
                                <div className="text-left flex-1 min-w-0 animate-in fade-in slide-in-from-left-2 duration-300">
                                    <div className="text-[13px] font-bold text-header truncate tracking-tight leading-tight">
                                        {data.name}
                                    </div>
                                    <div className="text-[10px] text-muted truncate tracking-tight leading-tight">
                                        {data.email}
                                    </div>
                                </div>
                            )}
                        </button>
                    </DropdownMenuTrigger>

                    {/* Bending line indicator on the right */}
                    <div
                        className={cn(
                            "absolute top-1/2 -translate-y-1/2 transition-all duration-300 pointer-events-none",
                            expanded ? "-right-3" : "-right-2",
                            isOpen
                                ? "opacity-100"
                                : "opacity-60 group-hover:opacity-100"
                        )}
                    >
                        <svg
                            width="12"
                            height="24"
                            viewBox="0 0 12 24"
                            fill="none"
                            className={cn(
                                "transition-all duration-300",
                                isOpen
                                    ? "text-accent-primary scale-110"
                                    : "text-muted group-hover:text-header"
                            )}
                            aria-hidden="true"
                        >
                            <path
                                d="M2 4C6 8 6 16 2 20"
                                stroke="currentColor"
                                strokeWidth="2.5"
                                strokeLinecap="round"
                                fill="none"
                            />
                        </svg>
                    </div>

                    <DropdownMenuContent
                        side="right"
                        align={expanded ? "end" : "center"}
                        sideOffset={expanded ? 16 : 20}
                        className="w-64 p-2 bg-surface/95 backdrop-blur-xl border border-border rounded-2xl shadow-2xl animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=right]:slide-in-from-left-2 origin-left z-[100]"
                    >
                        <div className="px-2 py-1.5 mb-2">
                            <div className="text-[11px] font-bold text-muted uppercase tracking-[0.1em]">Account Settings</div>
                        </div>

                        <div className="space-y-0.5">
                            {menuItems.map((item) => (
                                <DropdownMenuItem key={item.label} asChild>
                                    <Link
                                        to={item.href}
                                        className="flex items-center gap-3 p-2.5 hover:bg-elevated rounded-xl transition-all duration-200 cursor-pointer group hover:shadow-sm border border-transparent hover:border-border"
                                    >
                                        <div className="flex items-center gap-3 flex-1">
                                            <span className="text-muted group-hover:text-accent-primary transition-colors">
                                                {item.icon}
                                            </span>
                                            <span className="text-sm font-medium text-header tracking-tight leading-tight whitespace-nowrap group-hover:text-primary transition-colors">
                                                {item.label}
                                            </span>
                                        </div>
                                        {item.value && (
                                            <span
                                                className={cn(
                                                    "text-[9px] font-bold rounded-md py-0.5 px-1.5 tracking-tight uppercase border shadow-sm",
                                                    item.label === "Model"
                                                        ? "text-blue-500 bg-blue-500/10 border-blue-500/20"
                                                        : "text-purple-500 bg-purple-500/10 border-purple-500/20"
                                                )}
                                            >
                                                {item.value}
                                            </span>
                                        )}
                                    </Link>
                                </DropdownMenuItem>
                            ))}
                        </div>
                    </DropdownMenuContent>
                </div>
            </DropdownMenu>
        </div>
    );
}
