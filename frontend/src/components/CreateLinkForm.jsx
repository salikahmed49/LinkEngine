import React, { useState } from 'react';
import { Link2, CornerDownRight, AlertCircle, Loader2, Sparkles } from 'lucide-react';
import { createShortLink, DISPLAY_DOMAIN } from '../services/api';

const SAMPLES = [
  { url: 'https://github.com/torvalds/linux', alias: 'torvalds' },
  { url: 'https://fastapi.tiangolo.com', alias: 'fastapi' },
  { url: 'https://redis.io/docs/data-types/streams/', alias: 'streams' },
];

export default function CreateLinkForm({ onLinkCreated }) {
  const [url, setUrl] = useState('');
  const [alias, setAlias] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const isValidAlias = !alias || /^[a-zA-Z0-9_-]{3,10}$/.test(alias);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url.trim() || !isValidAlias) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await createShortLink(url, alias);
      onLinkCreated(result);
      setUrl('');
      setAlias('');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const applySample = (sample) => {
    setUrl(sample.url);
    setAlias(sample.alias);
    setError(null);
  };

  return (
    <div className="surface-panel create-panel">
      <div className="panel-top">
        <div className="panel-title-group">
          <Link2 size={16} strokeWidth={2} className="text-cyan" />
          <h2 className="panel-heading">Shorten URL</h2>
        </div>
        <div className="sample-presets">
          <span className="preset-label">Presets:</span>
          {SAMPLES.map((s, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => applySample(s)}
              className="preset-chip"
            >
              /{s.alias}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="form-stack">
        <div className="input-group">
          <label className="input-label" htmlFor="destination-url">
            Destination URL
          </label>
          <input
            id="destination-url"
            type="url"
            className="text-input"
            placeholder="https://example.com/long/path/to/resource"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            autoComplete="off"
            spellCheck="false"
          />
        </div>

        <div className="input-group">
          <div className="flex-between">
            <label className="input-label" htmlFor="custom-alias">
              Custom Slug <span className="text-dim">(optional)</span>
            </label>
            {alias && (
              <span className={`validation-tag mono ${isValidAlias ? 'valid' : 'invalid'}`}>
                {isValidAlias ? 'Valid' : '3-10 alphanumeric only'}
              </span>
            )}
          </div>

          <div className="slug-input-container">
            <span className="slug-prefix">/</span>
            <input
              id="custom-alias"
              type="text"
              className="text-input slug-input mono"
              placeholder="custom-slug"
              value={alias}
              onChange={(e) => setAlias(e.target.value)}
              pattern="^[a-zA-Z0-9_-]{3,10}$"
              autoComplete="off"
              spellCheck="false"
            />
          </div>

          <div className="slug-preview-bar">
            <span className="preview-label">Live Preview:</span>
            <span className="preview-url mono">
              {DISPLAY_DOMAIN}/<strong>{alias || 'auto-generated'}</strong>
            </span>
          </div>
        </div>

        <button
          type="submit"
          className="btn btn-action"
          disabled={isLoading || !url.trim() || !isValidAlias}
        >
          {isLoading ? (
            <>
              <Loader2 size={15} className="spin" strokeWidth={2} />
              <span>Routing & Caching...</span>
            </>
          ) : (
            <>
              <span>Generate Short Link</span>
              <kbd className="kbd-shortcut">↵</kbd>
            </>
          )}
        </button>
      </form>

      {error && (
        <div className="error-callout">
          <AlertCircle size={15} strokeWidth={2} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
