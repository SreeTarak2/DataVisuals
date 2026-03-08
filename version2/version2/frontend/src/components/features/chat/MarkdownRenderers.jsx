// frontend/src/components/features/chat/MarkdownRenderers.jsx
// Premium Claude-style markdown renderers for chat messages

import React, { useState, useCallback } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check, Code2, Table2, Quote, Terminal, FileCode } from 'lucide-react';
import { cn } from '@/lib/utils';

// ─────────────────────────────────────────────
// Code Block (Claude / ChatGPT style)
// ─────────────────────────────────────────────
const CodeBlock = ({ language, children }) => {
    const [copied, setCopied] = useState(false);
    const code = String(children).replace(/\n$/, '');

    const handleCopy = useCallback(async () => {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }, [code]);

    const LANG_LABELS = {
        js: 'JavaScript', javascript: 'JavaScript',
        ts: 'TypeScript', typescript: 'TypeScript',
        py: 'Python', python: 'Python',
        sql: 'SQL', bash: 'Bash', sh: 'Shell',
        json: 'JSON', html: 'HTML', css: 'CSS',
        jsx: 'React JSX', tsx: 'React TSX',
        r: 'R', java: 'Java', cpp: 'C++', c: 'C',
        go: 'Go', rust: 'Rust', ruby: 'Ruby',
        yaml: 'YAML', yml: 'YAML', xml: 'XML',
        md: 'Markdown', markdown: 'Markdown',
    };

    const langLabel = LANG_LABELS[language?.toLowerCase()] || language?.toUpperCase() || 'CODE';

    return (
        <div className="my-4 rounded-xl overflow-hidden border border-slate-700/60 bg-[#0d1117] shadow-lg">
            {/* Header bar */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-[#161b22] border-b border-slate-700/60">
                <div className="flex items-center gap-2">
                    <FileCode size={14} className="text-slate-400" />
                    <span className="text-xs font-medium text-slate-400 tracking-wide">{langLabel}</span>
                </div>
                <button
                    onClick={handleCopy}
                    className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-all duration-200",
                        copied
                            ? "bg-green-500/15 text-green-400"
                            : "hover:bg-slate-700/50 text-slate-400 hover:text-slate-200"
                    )}
                >
                    {copied ? <Check size={13} /> : <Copy size={13} />}
                    {copied ? 'Copied' : 'Copy'}
                </button>
            </div>
            {/* Code content */}
            <div className="overflow-x-auto">
                <SyntaxHighlighter
                    language={language || 'text'}
                    style={oneDark}
                    customStyle={{
                        margin: 0,
                        padding: '16px 20px',
                        background: 'transparent',
                        fontSize: '13.5px',
                        lineHeight: '1.65',
                    }}
                    codeTagProps={{
                        style: { fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace" }
                    }}
                    showLineNumbers={code.split('\n').length > 4}
                    lineNumberStyle={{
                        color: '#3b4252',
                        paddingRight: '16px',
                        fontSize: '12px',
                        minWidth: '2.5em',
                    }}
                >
                    {code}
                </SyntaxHighlighter>
            </div>
        </div>
    );
};

// ─────────────────────────────────────────────
// Inline Code
// ─────────────────────────────────────────────
const InlineCode = ({ children }) => (
    <code className="bg-slate-800/80 text-cyan-300 px-1.5 py-0.5 rounded-md text-[13px] font-mono border border-slate-700/40">
        {children}
    </code>
);

// ─────────────────────────────────────────────
// Table (Premium with scroll container)
// ─────────────────────────────────────────────
const TableBlock = ({ children }) => (
    <div className="my-4 rounded-xl overflow-hidden border border-slate-700/60 shadow-lg">
        <div className="flex items-center gap-2 px-4 py-2.5 bg-[#161b22] border-b border-slate-700/60">
            <Table2 size={14} className="text-slate-400" />
            <span className="text-xs font-medium text-slate-400 tracking-wide">TABLE</span>
        </div>
        <div className="overflow-x-auto bg-[#0d1117]">
            <table className="w-full text-sm border-collapse">
                {children}
            </table>
        </div>
    </div>
);

const TableHead = ({ children }) => (
    <thead className="bg-[#161b22]">
        {children}
    </thead>
);

const TableRow = ({ children, isHeader }) => (
    <tr className={cn(
        "border-b border-slate-700/40 transition-colors",
        !isHeader && "hover:bg-slate-800/40"
    )}>
        {children}
    </tr>
);

const TableHeader = ({ children }) => (
    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider whitespace-nowrap">
        {children}
    </th>
);

const TableCell = ({ children }) => (
    <td className="px-4 py-3 text-slate-300 whitespace-nowrap text-[13.5px]">
        {children}
    </td>
);

// ─────────────────────────────────────────────
// Blockquote / Callout
// ─────────────────────────────────────────────
const BlockquoteBlock = ({ children }) => (
    <div className="my-4 flex rounded-xl overflow-hidden border border-blue-500/20 bg-blue-500/5">
        <div className="w-1 bg-blue-500/60 flex-shrink-0" />
        <div className="px-4 py-3 text-[15px] text-blue-200/90 leading-relaxed [&>p]:mb-0">
            {children}
        </div>
    </div>
);

// ─────────────────────────────────────────────
// Headings
// ─────────────────────────────────────────────
const H1 = ({ children }) => (
    <h1 className="text-xl font-bold text-white mt-6 mb-3 pb-2 border-b border-slate-700/50">
        {children}
    </h1>
);

const H2 = ({ children }) => (
    <h2 className="text-lg font-semibold text-white mt-5 mb-2.5">
        {children}
    </h2>
);

const H3 = ({ children }) => (
    <h3 className="text-base font-semibold text-slate-200 mt-4 mb-2">
        {children}
    </h3>
);

// ─────────────────────────────────────────────
// Text Elements
// ─────────────────────────────────────────────
const Paragraph = ({ children }) => (
    <p className="mb-3 last:mb-0 leading-[1.75] text-[15px] text-slate-200 break-words">
        {children}
    </p>
);

const Strong = ({ children }) => (
    <strong className="font-semibold text-white">
        {children}
    </strong>
);

const Emphasis = ({ children }) => (
    <em className="italic text-slate-300">
        {children}
    </em>
);

const Link = ({ href, children }) => (
    <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-400 hover:text-blue-300 underline underline-offset-2 decoration-blue-400/40 hover:decoration-blue-300/60 transition-colors"
    >
        {children}
    </a>
);

// ─────────────────────────────────────────────
// Lists
// ─────────────────────────────────────────────
const UnorderedList = ({ children }) => (
    <ul className="mb-3 ml-1 space-y-1.5 list-none">
        {children}
    </ul>
);

const OrderedList = ({ children }) => (
    <ol className="mb-3 ml-1 space-y-1.5 list-none counter-reset-[list-counter]">
        {children}
    </ol>
);

const ListItem = ({ children, ordered, index }) => (
    <li className="flex gap-2.5 text-[15px] leading-[1.75] text-slate-200">
        <span className="flex-shrink-0 mt-[3px] text-slate-500 select-none">
            {ordered ? `${index + 1}.` : '•'}
        </span>
        <span className="flex-1 break-words">{children}</span>
    </li>
);

// ─────────────────────────────────────────────
// Horizontal Rule
// ─────────────────────────────────────────────
const HorizontalRule = () => (
    <hr className="my-6 border-none h-px bg-gradient-to-r from-transparent via-slate-600/50 to-transparent" />
);

// ─────────────────────────────────────────────
// Export renderers object for ReactMarkdown
// ─────────────────────────────────────────────
export const markdownComponents = {
    // Code
    code({ node, inline, className, children, ...props }) {
        const match = /language-(\w+)/.exec(className || '');
        if (!inline && (match || String(children).includes('\n'))) {
            return <CodeBlock language={match?.[1]}>{children}</CodeBlock>;
        }
        return <InlineCode {...props}>{children}</InlineCode>;
    },

    // Blocks
    pre({ children }) {
        // The pre tag wraps code blocks — we handle rendering inside `code`
        return <>{children}</>;
    },
    blockquote({ children }) {
        return <BlockquoteBlock>{children}</BlockquoteBlock>;
    },

    // Table
    table({ children }) { return <TableBlock>{children}</TableBlock>; },
    thead({ children }) { return <TableHead>{children}</TableHead>; },
    tr({ children, isHeader }) { return <TableRow isHeader={isHeader}>{children}</TableRow>; },
    th({ children }) { return <TableHeader>{children}</TableHeader>; },
    td({ children }) { return <TableCell>{children}</TableCell>; },

    // Headings
    h1({ children }) { return <H1>{children}</H1>; },
    h2({ children }) { return <H2>{children}</H2>; },
    h3({ children }) { return <H3>{children}</H3>; },
    h4({ children }) { return <h4 className="text-sm font-semibold text-slate-200 mt-3 mb-1.5">{children}</h4>; },

    // Text
    p({ children }) { return <Paragraph>{children}</Paragraph>; },
    strong({ children }) { return <Strong>{children}</Strong>; },
    em({ children }) { return <Emphasis>{children}</Emphasis>; },
    a({ href, children }) { return <Link href={href}>{children}</Link>; },

    // Lists
    ul({ children }) { return <UnorderedList>{children}</UnorderedList>; },
    ol({ children }) { return <OrderedList>{children}</OrderedList>; },
    li({ children, ordered, index }) { return <ListItem ordered={ordered} index={index}>{children}</ListItem>; },

    // Separators
    hr() { return <HorizontalRule />; },
};

// Streaming version (slightly lighter — no line numbers, smaller)
export const streamingMarkdownComponents = {
    ...markdownComponents,
    code({ node, inline, className, children, ...props }) {
        const match = /language-(\w+)/.exec(className || '');
        if (!inline && (match || String(children).includes('\n'))) {
            return <CodeBlock language={match?.[1]}>{children}</CodeBlock>;
        }
        return <InlineCode {...props}>{children}</InlineCode>;
    },
};

export default markdownComponents;
