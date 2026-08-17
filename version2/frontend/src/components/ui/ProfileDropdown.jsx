import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { Settings, CreditCard, FileText, LogOut, User, ChevronsUpDown } from "lucide-react";
import { Link } from "react-router-dom";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import OpenRouter from "@lobehub/icons/es/OpenRouter";

const ROLE_COLORS = {
    owner:  'bg-amber-500/10 text-amber-400 border-amber-500/20',
    admin:  'bg-blue-500/10 text-blue-400 border-blue-500/20',
    member: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    viewer: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
};

const ROLE_LABELS = {
    owner:  'Owner',
    admin:  'Admin',
    member: 'Member',
    viewer: 'Viewer',
};

const ItemContent = ({ item }) => (
    <>
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
                        : "text-orange-500 bg-orange-500/10 border-orange-500/20"
                )}
            >
                {item.value}
            </span>
        )}
    </>
);

export function ProfileDropdown({
    data,
    role,
    className,
    expanded = true,
    onLogout,
    ...props
}) {
    const roleColor = ROLE_COLORS[role] || ROLE_COLORS.viewer;
    const roleLabel = ROLE_LABELS[role] || '';

    const [isOpen, setIsOpen] = useState(false);

    const menuItems = [
        {
            label: "Profile",
            href: "/app/settings?tab=general",
            icon: <User className="w-4 h-4" />,
        },
        {
            label: "Model",
            value: data.model,
            icon: <OpenRouter className="w-4 h-4" />,
        },
        // {
        //     label: "Subscription",
        //     value: data.subscription,
        //     href: "/app/settings/billing",
        //     icon: <CreditCard className="w-4 h-4" />,
        // },
        {
            label: "Settings",
            href: "/app/settings?tab=workspace",
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
                                "flex items-center gap-2.5 rounded-md hover:bg-[var(--bg-active)] transition-all duration-200 focus:outline-none cursor-pointer w-full text-left border border-transparent",
                                expanded ? "p-1.5" : "p-1.5 justify-center"
                            )}
                        >
                            <div className="relative shrink-0">
                                <div className={cn(
                                    "rounded-md overflow-hidden bg-primary shrink-0",
                                    expanded ? "w-8 h-8" : "w-8 h-8"
                                )}>
                                    <img
                                        src={data.avatar}
                                        alt={data.name}
                                        className="w-full h-full object-cover"
                                    />
                                </div>
                            </div>
                            {expanded && (
                                <>
                                    <div className="text-left flex-1 min-w-0">
                                        <div className="text-[13px] font-medium text-[var(--text-primary)] truncate leading-tight">
                                            {data.name}
                                        </div>
                                        <div className="flex items-center gap-1.5 mt-0.5">
                                            <span className="text-[11px] text-[var(--text-secondary)] truncate leading-tight">
                                                {data.email}
                                            </span>
                                            <span className={cn(
                                                "inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider leading-none border shrink-0",
                                                roleColor
                                            )}>
                                                {roleLabel}
                                            </span>
                                        </div>
                                    </div>
                                    <ChevronsUpDown className="w-3.5 h-3.5 text-[var(--text-secondary)] shrink-0" />
                                </>
                            )}
                        </button>
                    </DropdownMenuTrigger>

                    <DropdownMenuContent
                        side="right"
                        align={expanded ? "end" : "center"}
                        sideOffset={expanded ? 16 : 20}
                        className="w-64 p-2 bg-surface/95 backdrop-blur-xl border border-border rounded-2xl shadow-2xl animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=right]:slide-in-from-left-2 origin-left z-[100]"
                    >
                        <div className="px-2 py-1.5 mb-2 space-y-1.5">
                            <div className="text-[11px] font-bold text-muted uppercase tracking-[0.1em]">Account Settings</div>
                            <div className="flex items-center gap-2">
                                <div className="w-6 h-6 rounded overflow-hidden bg-primary shrink-0">
                                    <img
                                        src={data.avatar}
                                        alt={data.name}
                                        className="w-full h-full object-cover"
                                    />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-[13px] font-medium text-[var(--text-primary)] truncate leading-tight">
                                        {data.name}
                                    </div>
                                    <div className="flex items-center gap-1">
                                        <span className="text-[10px] text-[var(--text-secondary)] truncate">{data.email}</span>
                                        <span className={cn(
                                            "inline-flex items-center rounded-full px-1.5 py-[1px] text-[8px] font-bold uppercase tracking-wider leading-none border shrink-0",
                                            roleColor
                                        )}>
                                            {roleLabel}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-0.5">
                            {menuItems.map((item) => (
                                <DropdownMenuItem key={item.label} asChild>
                                    {item.href ? (
                                        <Link
                                            to={item.href}
                                            className="flex items-center gap-3 p-2.5 hover:bg-elevated rounded-xl transition-all duration-200 cursor-pointer group hover:shadow-sm border border-transparent hover:border-border"
                                        >
                                            <ItemContent item={item} />
                                        </Link>
                                    ) : (
                                        <div className="flex items-center gap-3 p-2.5 rounded-xl border border-transparent">
                                            <ItemContent item={item} />
                                        </div>
                                    )}
                                </DropdownMenuItem>
                            ))}
                        </div>

                        {onLogout && (
                            <>
                                <DropdownMenuSeparator className="my-2 bg-border/50" />
                                <DropdownMenuItem asChild>
                                    <button
                                        type="button"
                                        onClick={onLogout}
                                        className="w-full flex items-center gap-3 p-2.5 hover:bg-red-500/10 rounded-xl transition-all duration-200 cursor-pointer group hover:shadow-sm border border-transparent hover:border-red-500/20 focus:outline-none"
                                    >
                                        <div className="flex items-center gap-3 flex-1">
                                            <span className="text-muted group-hover:text-red-400 transition-colors">
                                                <LogOut className="w-4 h-4" />
                                            </span>
                                            <span className="text-sm font-medium text-header tracking-tight leading-tight whitespace-nowrap group-hover:text-red-400 transition-colors">
                                                Log Out
                                            </span>
                                        </div>
                                    </button>
                                </DropdownMenuItem>
                            </>
                        )}
                    </DropdownMenuContent>
                </div>
            </DropdownMenu>
        </div>
    );
}
