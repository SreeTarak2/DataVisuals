/**
 * ChatPanel — backward-compatible wrapper around SideChatPanel.
 *
 * This file exists so existing consumers (DashboardLayout, SqlEditorPage)
 * continue to work without changes. New code should import SideChatPanel directly.
 */
import SideChatPanel from './SideChatPanel';

const ChatPanel = (props) => <SideChatPanel {...props} />;

export default ChatPanel;
