"use client"

import * as React from "react"
import { Trash2, AlertTriangle } from "lucide-react"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function DeleteConfirmDialog({
    open,
    onOpenChange,
    onConfirm,
    title = "Delete Conversation",
    description = "Are you sure you want to delete this conversation? This action cannot be undone.",
    itemName = "",
}) {
    const handleConfirm = () => {
        onConfirm?.();
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                className="sm:max-w-md border-zinc-800 bg-zinc-950 text-zinc-100 shadow-2xl"
                showCloseButton={false}
            >
                <DialogHeader className="space-y-4">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-red-500/10 ring-1 ring-red-500/20">
                        <AlertTriangle className="h-7 w-7 text-red-500" />
                    </div>
                    <DialogTitle className="text-center text-xl font-semibold text-zinc-100">
                        {title}
                    </DialogTitle>
                    <DialogDescription className="text-center text-zinc-400">
                        {description}
                        {itemName && (
                            <span className="mt-2 block text-sm font-medium text-zinc-300">
                                "{itemName}"
                            </span>
                        )}
                    </DialogDescription>
                </DialogHeader>

                <DialogFooter className="mt-6 flex-col gap-3 sm:flex-row">
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        className="w-full border-zinc-700 bg-transparent text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 sm:w-auto"
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleConfirm}
                        className="w-full bg-red-600 text-white hover:bg-red-700 focus:ring-red-500 sm:w-auto"
                    >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
