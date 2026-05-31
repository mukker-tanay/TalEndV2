import { useState } from "react";
import { useRouter } from "next/router";
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Login failed");

      localStorage.setItem("token", data.access_token);
      localStorage.setItem("role", data.role || "user");
      console.log("Token saved:", data.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <form
        onSubmit={handleLogin}
        className="bg-slate-900/60 backdrop-blur-md p-8 rounded-2xl border border-slate-800 shadow-2xl w-full max-w-md transition-all duration-300 hover:border-slate-700/80"
      >
        <div className="text-center mb-8">
          <h2 className="text-3xl font-extrabold text-slate-100 tracking-tight">JobNoc Portal</h2>
          <p className="mt-2 text-sm text-slate-400">Enter recruiter credentials to access</p>
        </div>
        
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Email Address</label>
            <input
              type="email"
              placeholder="recruiter@agency.com"
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 transition-all duration-200"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Password</label>
            <input
              type="password"
              placeholder="••••••••"
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 transition-all duration-200"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
        </div>

        {error && <p className="text-red-400 mt-4 text-xs font-medium bg-red-500/10 border border-red-500/20 p-2.5 rounded-lg">{error}</p>}
        
        <button
          type="submit"
          className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-xl mt-6 shadow-lg shadow-indigo-600/20 hover:shadow-indigo-500/30 transition-all duration-200"
        >
          Sign In
        </button>

        <p className="mt-6 text-center text-xs text-slate-400">
          Not registered?{' '}
          <a href="/register" className="text-indigo-400 hover:underline font-medium">
            Create account
          </a>
        </p>
      </form>
    </div>
  );
}

