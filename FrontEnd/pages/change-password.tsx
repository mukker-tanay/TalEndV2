import { useState, useEffect } from "react";
import { useRouter } from "next/router";

// Force production API URL if running on the live domain, ignoring the hardcoded localhost in .env
let API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
if (typeof window !== 'undefined' && window.location.hostname === 'jobnoc.com') {
  API_URL = 'https://jobnoc.com/api';
}

export default function ChangePassword() {
  const router = useRouter();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const requirePassChange = localStorage.getItem("require_password_change");
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
    } else if (!requirePassChange) {
      router.push("/dashboard");
    }
  }, [router]);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    if (newPassword.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    setLoading(true);
    const token = localStorage.getItem("token");

    try {
      const res = await fetch(`${API_URL}/auth/change-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Failed to update password");

      localStorage.removeItem("require_password_change");
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("require_password_change");
    router.push("/login");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 px-4">
      <form
        onSubmit={handleChangePassword}
        className="bg-gray-50 p-8 rounded-2xl border border-gray-200 shadow-sm w-full max-w-md transition-all duration-300"
      >
        <div className="text-center mb-8">
          <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight">Security Update</h2>
          <p className="mt-2 text-sm text-gray-500">Please update your temporary password to continue</p>
        </div>
        
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">Temporary Password</label>
            <input
              type="password"
              placeholder="••••••••"
              className="w-full bg-gray-50 border border-gray-300 rounded-xl px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all duration-200"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              required
            />
          </div>
          
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">New Password</label>
            <input
              type="password"
              placeholder="••••••••"
              className="w-full bg-gray-50 border border-gray-300 rounded-xl px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all duration-200"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">Confirm New Password</label>
            <input
              type="password"
              placeholder="••••••••"
              className="w-full bg-gray-50 border border-gray-300 rounded-xl px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all duration-200"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
        </div>

        {error && <p className="text-red-600 mt-4 text-xs font-medium bg-red-50 border border-red-200 p-2.5 rounded-lg">{error}</p>}
        
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gray-900 hover:bg-black disabled:opacity-50 text-white font-semibold py-2.5 rounded-xl mt-6 shadow-sm transition-all duration-200"
        >
          {loading ? "Updating..." : "Update Password & Continue"}
        </button>

        <button
          type="button"
          onClick={handleLogout}
          className="w-full text-gray-500 hover:text-gray-700 text-sm font-semibold py-2.5 mt-2 transition-all duration-200"
        >
          Cancel and Sign Out
        </button>
      </form>
    </div>
  );
}
