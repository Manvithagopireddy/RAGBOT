import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Bot, FileText, Activity, BarChart2, ShieldCheck, LogIn, LogOut, User as UserIcon } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { HealthStatus } from '../types';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    api.getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const navItems = [
    { name: 'Chat', path: '/', icon: Bot },
    { name: 'Documents', path: '/documents', icon: FileText },
    { name: 'Diagnostics', path: '/diagnostics', icon: Activity },
    { name: 'Analytics', path: '/analytics', icon: BarChart2 },
  ];

  return (
    <header className="h-14 gap-1 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 px-2 sm:px-4 flex items-center justify-between">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 group-hover:scale-105 transition-transform">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="font-semibold text-sm tracking-tight flex items-center gap-1.5 text-slate-100">
              RAGBOT
              <span className="hidden xl:inline text-[10px] font-mono px-1.5 py-0.5 rounded bg-teal-950 text-teal-400 border border-teal-800/40">
                v2.0 Enterprise
              </span>
            </div>
          </div>
        </Link>

        {/* Global health dot */}
        <div className="hidden xl:flex items-center gap-1.5 ml-3 pl-3 border-l border-slate-800 text-xs text-slate-400">
          <span className={`w-2 h-2 rounded-full ${health ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
          <span className="text-[11px] font-mono">{health ? 'Hybrid RAG Online' : 'Connecting...'}</span>
        </div>
      </div>

      {/* Nav items */}
      <nav className="flex items-center gap-1 sm:gap-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
          return (
            <Link
              key={item.path}
              to={item.path}
              aria-label={item.name}
              title={item.name}
              className={`px-2 lg:px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${
                isActive
                  ? 'bg-slate-800 text-teal-400 border border-slate-700/80 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span className="hidden lg:inline">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* User profile / login */}
      <div className="flex items-center gap-2">
        {user ? (
          <div className="flex items-center gap-2">
            <div className="hidden md:flex flex-col text-right">
              <span className="text-xs font-medium text-slate-200">{user.username}</span>
              <span className="text-[10px] text-slate-400">{user.role}</span>
            </div>
            <button
              onClick={logout}
              title="Logout"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-teal-600 hover:bg-teal-500 text-white flex items-center gap-1.5 shadow-sm transition-colors"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Sign In</span>
          </Link>
        )}
      </div>
    </header>
  );
};
