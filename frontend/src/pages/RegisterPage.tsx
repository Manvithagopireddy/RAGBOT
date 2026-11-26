import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bot, UserPlus, AlertCircle } from 'lucide-react';
import { api } from '../api/client';

export const RegisterPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await api.register({
        username: username.trim(),
        email: email.trim(),
        password,
      });
      navigate('/login');
    } catch (err: any) {
      setError(err.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex items-center justify-center p-4">
      <div className="w-full max-w-sm p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-5">
        <div className="text-center space-y-1">
          <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-400 flex items-center justify-center mx-auto mb-2">
            <Bot className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-slate-100">Create an Account</h2>
          <p className="text-xs text-slate-400">Join RAGBOT to manage your personalized documents.</p>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label htmlFor="register-username" className="block text-slate-300 font-medium mb-1">Username</label>
            <input
              id="register-username"
              type="text"
              required
              minLength={3}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. jdoe"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500"
            />
          </div>

          <div>
            <label htmlFor="register-email" className="block text-slate-300 font-medium mb-1">Email</label>
            <input
              id="register-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. jdoe@example.com"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500"
            />
          </div>

          <div>
            <label htmlFor="register-password" className="block text-slate-300 font-medium mb-1">Password</label>
            <input
              id="register-password"
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 6 characters"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-xl font-semibold bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white shadow-sm transition-all flex items-center justify-center gap-1.5"
          >
            <UserPlus className="w-4 h-4" />
            <span>{loading ? 'Registering…' : 'Create Account'}</span>
          </button>
        </form>

        <div className="text-center text-xs text-slate-400 pt-2">
          Already have an account?{' '}
          <Link to="/login" className="text-teal-400 hover:underline font-medium">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
};
