/**
 * VersionSwitcher — Navigate Between Message Versions (← 1/2 →)
 *
 * Displays a version chip below AI messages when multiple versions exist.
 * Allows the user to:
 *   - Navigate between versions using ← and → arrows
 *   - See which version is currently displayed (1/3)
 *   - Regenerate to create a new version
 *
 * Usage:
 *   <VersionSwitcher
 *     versions={[msg1, msg2, msg3]}
 *     currentVersion={1}
 *     onSwitch={(versionIndex) => ...}
 *     onRegenerate={() => ...}
 *   />
 */
import React, { memo } from 'react';
import { RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';

const VersionSwitcher = memo(({
  versions = [],
  currentVersion = 0,
  onSwitch,
  onRegenerate,
}) => {
  if (versions.length <= 1) return null;

  const totalVersions = versions.length;
  const isFirst = currentVersion === 0;
  const isLast = currentVersion === totalVersions - 1;

  // Get a short diff label for the current version
  const currentMetadata = versions[currentVersion]?.metadata || {};
  const getVersionLabel = () => {
    if (currentMetadata.model) {
      return `v${currentVersion + 1} (${currentMetadata.model.split('/').pop()?.slice(0, 12) || 'default'})`;
    }
    return `v${currentVersion + 1}`;
  };

  return (
    <div className="version-switcher">
      <div className="version-switcher__nav">
        <button
          className={`version-switcher__btn ${isFirst ? 'version-switcher__btn--disabled' : ''}`}
          onClick={() => !isFirst && onSwitch(currentVersion - 1)}
          disabled={isFirst}
          title="Previous version"
        >
          <ChevronLeft size={11} />
        </button>

        <span className="version-switcher__indicator">
          {getVersionLabel()}
          <span className="version-switcher__total">
            / {totalVersions}
          </span>
        </span>

        <button
          className={`version-switcher__btn ${isLast ? 'version-switcher__btn--disabled' : ''}`}
          onClick={() => !isLast && onSwitch(currentVersion + 1)}
          disabled={isLast}
          title="Next version"
        >
          <ChevronRight size={11} />
        </button>
      </div>

      <button
        className="version-switcher__regen"
        onClick={onRegenerate}
        title="Regenerate new version"
      >
        <RefreshCw size={11} />
        <span>Regenerate</span>
      </button>
    </div>
  );
});

VersionSwitcher.displayName = 'VersionSwitcher';
export default VersionSwitcher;
