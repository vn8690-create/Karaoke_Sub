'use client';

import { useState, useEffect } from 'react';
import { X, KeyRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { setAccessToken, getAccessToken, clearAccessToken } from '@/lib/api';

export function AuthBanner() {
  const [token, setToken] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showInput, setShowInput] = useState(false);

  useEffect(() => {
    const storedToken = getAccessToken();
    if (storedToken) {
      setIsAuthenticated(true);
      setToken(storedToken.substring(0, 8) + '...');
    } else {
      setShowInput(true);
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (token.trim()) {
      setAccessToken(token.trim());
      setIsAuthenticated(true);
      setShowInput(false);
      // Reload to fetch jobs with auth
      window.location.reload();
    }
  };

  const handleLogout = () => {
    clearAccessToken();
    setIsAuthenticated(false);
    setToken('');
    setShowInput(true);
    window.location.reload();
  };

  if (isAuthenticated && !showInput) {
    return (
      <div className="bg-green-500/10 border border-green-500/20 text-green-400 px-4 py-2 rounded-lg flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4" />
          <span>Authenticated</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          className="h-6 px-2 text-xs text-green-400 hover:text-green-300"
        >
          Logout
        </Button>
      </div>
    );
  }

  return (
    <div className="bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 px-4 py-3 rounded-lg">
      <div className="flex items-start gap-3">
        <KeyRound className="h-5 w-5 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <p className="font-medium mb-2">Authentication Required</p>
          {showInput ? (
            <form onSubmit={handleSubmit} className="flex gap-2">
              <Input
                type="password"
                placeholder="Enter access token"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="flex-1 bg-[var(--secondary)] border-[var(--card-border)] text-sm"
              />
              <Button type="submit" size="sm" disabled={!token.trim()}>
                Authenticate
              </Button>
            </form>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowInput(true)}
              className="mt-1"
            >
              Enter Token
            </Button>
          )}
          <p className="text-xs mt-2 text-[var(--text-muted)]">
            Contact an admin to get an access token
          </p>
        </div>
        {showInput && (
          <button
            onClick={() => setShowInput(false)}
            className="text-[var(--text-muted)] hover:text-[var(--text)]"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

