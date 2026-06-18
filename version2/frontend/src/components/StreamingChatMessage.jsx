import React, { useState, useEffect, useRef } from "react";

/**
 * StreamingChatMessage
 *
 * Production-grade streaming chat component.
 * Handles:
 * - Real-time token streaming
 * - Thinking step indicators
 * - Fallback rendering when no tokens arrive
 * - Error states with recovery
 * - Loading/empty states
 */
export function StreamingChatMessage({
  query,
  datasetId,
  userId,
  conversationId,
  onComplete,
  onError,
  endpoint = "/api/chat/stream", // default endpoint
}) {
  const [content, setContent] = useState("");
  const [hasStarted, setHasStarted] = useState(false);
  const [hasTokens, setHasTokens] = useState(false);
  const [thinkingSteps, setThinkingSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState(null);
  const [isError, setIsError] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const contentRef = useRef("");
  const abortControllerRef = useRef(null);

  useEffect(() => {
    if (!query || !datasetId || !userId) {
      setIsError(true);
      setErrorMessage("Missing required parameters: query, datasetId, userId");
      return;
    }

    const streamChat = async () => {
      setIsLoading(true);
      setHasStarted(true);
      contentRef.current = "";
      setContent("");
      setHasTokens(false);
      setThinkingSteps([]);
      setIsError(false);
      setErrorMessage("");

      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          body: JSON.stringify({
            query,
            dataset_id: datasetId,
            user_id: userId,
            conversation_id: conversationId || null,
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const jsonStr = line.slice(6);

            try {
              const event = JSON.parse(jsonStr);
              handleStreamEvent(event);
            } catch (e) {
              console.error("Failed to parse stream event:", e);
            }
          }
        }

        // Handle any remaining buffer
        if (buffer.startsWith("data: ")) {
          try {
            const event = JSON.parse(buffer.slice(6));
            handleStreamEvent(event);
          } catch (e) {
            console.error("Failed to parse final stream event:", e);
          }
        }
      } catch (err) {
        if (err.name !== "AbortError") {
          console.error("Stream error:", err);
          setIsError(true);
          setErrorMessage(
            err.message || "An error occurred while streaming the response."
          );
          if (onError) onError(err);
        }
      } finally {
        setIsLoading(false);
      }
    };

    streamChat();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [query, datasetId, userId, conversationId, endpoint, onComplete, onError]);

  const handleStreamEvent = (event) => {
    if (event.type === "thinking_step") {
      setCurrentStep(event.label);
      setThinkingSteps((prev) => [...prev, event]);
    } else if (event.type === "token") {
      setHasTokens(true);
      contentRef.current += event.content;
      setContent(contentRef.current);
    } else if (event.type === "response_complete") {
      // Fallback: if no tokens arrived, use the full_response
      if (!hasTokens && event.full_response) {
        contentRef.current = event.full_response;
        setContent(event.full_response);
      }
    } else if (event.type === "error") {
      setIsError(true);
      setErrorMessage(event.content || "An unknown error occurred.");
    } else if (event.type === "done") {
      setCurrentStep(null);
      if (onComplete) {
        onComplete({
          content: contentRef.current,
          hasTokens,
          thinkingSteps,
        });
      }
    } else if (event.type === "chart") {
      // Chart events can be handled separately or included in metadata
      console.log("Chart config received:", event.chart_config);
    }
  };

  // Render thinking steps indicator
  const renderThinkingIndicator = () => {
    if (!isLoading && !currentStep) return null;
    return (
      <div className="thinking-indicator">
        <div className="spinner" />
        <span className="thinking-text">
          {currentStep || "Processing..."}
        </span>
      </div>
    );
  };

  // Render message content
  const renderContent = () => {
    if (isError) {
      return (
        <div className="error-message">
          <strong>Error:</strong> {errorMessage}
        </div>
      );
    }

    if (!hasStarted) {
      return <div className="empty-state">Ready to analyze...</div>;
    }

    if (isLoading && !content) {
      return (
        <div className="loading-state">
          <div className="spinner" />
          Loading response...
        </div>
      );
    }

    return (
      <div className="message-content">
        {content}
        {isLoading && <span className="cursor" />}
      </div>
    );
  };

  return (
    <div className="streaming-chat-message">
      {renderThinkingIndicator()}
      {renderContent()}
    </div>
  );
}

export default StreamingChatMessage;
