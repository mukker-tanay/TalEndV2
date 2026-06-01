import { useEffect, useState } from "react";
import { useRouter } from "next/router";

// Force production API URL if running on the live domain, ignoring the hardcoded localhost in .env
let API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
if (typeof window !== 'undefined' && window.location.hostname === 'jobnoc.com') {
  API_URL = 'https://jobnoc.com/api';
}

type UserData = {
  name?: string;
  email: string;
  role: string;
};

export default function AdminDashboard() {
  const router = useRouter();
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [createMsg, setCreateMsg] = useState("");
  
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const role = typeof window !== "undefined" ? localStorage.getItem("role") : null;

  useEffect(() => {
    if (!token) {
      router.push("/login");
    } else if (role !== "admin") {
      router.push("/dashboard"); // Redirect non-admins
    } else {
      fetchUsers();
    }
  }, []);

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${API_URL}/auth/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    } catch (error) {
      console.error("Failed to fetch users", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateMsg("");
    
    try {
      const res = await fetch(`${API_URL}/auth/admin/users`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: newName,
          email: newEmail,
          password: newPassword,
          role: newRole,
        }),
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to create user");
      
      setCreateMsg("User created successfully!");
      setNewName("");
      setNewEmail("");
      setNewPassword("");
      setNewRole("user");
      fetchUsers();
    } catch (err: any) {
      setCreateMsg(err.message);
    }
  };

  const handleRoleChange = async (email: string, currentRole: string) => {
    const nextRole = currentRole === "admin" ? "user" : "admin";
    if (!confirm(`Are you sure you want to change ${email} to ${nextRole}?`)) return;

    try {
      const res = await fetch(`${API_URL}/auth/admin/users/${email}/role`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ role: nextRole }),
      });
      
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to update role");
      }
      
      fetchUsers();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    router.push("/");
  };

  if (loading) return <div className="h-screen bg-slate-950 text-slate-400 flex items-center justify-center font-semibold">Loading Admin Panel...</div>;

  return (
    <div className="flex h-screen bg-slate-950">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800/80 p-6 flex flex-col justify-between">
        <div>
          <div className="mb-10 px-2">
            <h1 className="text-2xl font-black text-indigo-400 tracking-tight">JobNoc</h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mt-1">Super Admin</p>
          </div>
          
          <nav className="space-y-1.5">
            <button
              onClick={() => router.push("/dashboard")}
              className="text-left w-full py-2.5 px-4 rounded-xl text-slate-300 hover:bg-slate-800 hover:text-slate-100 font-semibold transition-all duration-150 text-sm flex items-center gap-3"
            >
              Recruiter Workspace
            </button>
            <button
              className="text-left w-full py-2.5 px-4 rounded-xl text-indigo-300 bg-indigo-500/10 font-bold transition-all duration-150 text-sm flex items-center gap-3 border border-indigo-500/20"
            >
              Access Management
            </button>
          </nav>
        </div>

        <button
          onClick={handleLogout}
          className="text-left w-full py-2.5 px-4 text-red-400 hover:bg-red-500/10 hover:text-red-300 rounded-xl font-semibold transition-all duration-150 text-sm flex items-center gap-3"
        >
          Sign Out
        </button>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-8 lg:p-10">
        <header className="mb-8">
          <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight">Access Management</h1>
          <p className="text-sm text-slate-400 mt-1">Control who can access the recruiter workspace and assign administrative privileges</p>
        </header>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Create User Form */}
          <div className="xl:col-span-1">
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-xl sticky top-8">
              <h2 className="text-lg font-bold text-slate-100 mb-4">Provision New Account</h2>
              
              <form onSubmit={handleCreateUser} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Full Name</label>
                  <input
                    type="text"
                    required
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-all text-sm"
                    placeholder="Jane Doe"
                  />
                </div>
                
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Email Address</label>
                  <input
                    type="email"
                    required
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-all text-sm"
                    placeholder="jane@agency.com"
                  />
                </div>
                
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Temporary Password</label>
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-all text-sm"
                    placeholder="••••••••"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Access Role</label>
                  <select 
                    value={newRole} 
                    onChange={(e) => setNewRole(e.target.value)}
                    className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-2 text-slate-100 focus:outline-none focus:border-indigo-500 transition-all text-sm appearance-none"
                  >
                    <option value="user">Standard User (Recruiter)</option>
                    <option value="admin">Administrator</option>
                  </select>
                </div>
                
                <button
                  type="submit"
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-xl mt-2 shadow-lg shadow-indigo-600/20 transition-all duration-200 text-sm"
                >
                  Create Account
                </button>

                {createMsg && (
                  <div className={`mt-4 p-3 rounded-xl text-xs font-medium border ${createMsg.includes("successfully") ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"}`}>
                    {createMsg}
                  </div>
                )}
              </form>
            </div>
          </div>

          {/* User Ledger */}
          <div className="xl:col-span-2">
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
              <div className="p-5 border-b border-slate-800 flex justify-between items-center bg-slate-900/80">
                <h2 className="text-lg font-bold text-slate-100">Registered Users Ledger</h2>
                <span className="text-xs font-semibold text-slate-400 bg-slate-800 px-3 py-1 rounded-full border border-slate-700">
                  {users.length} Total
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse">
                  <thead className="bg-slate-850/50 border-b border-slate-800 text-slate-300 font-semibold text-xs tracking-wider uppercase">
                    <tr>
                      <th className="p-4">Name</th>
                      <th className="p-4">Email Address</th>
                      <th className="p-4">Role</th>
                      <th className="p-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80">
                    {users.map((u, i) => (
                      <tr key={i} className="hover:bg-slate-800/20 transition-all duration-150">
                        <td className="p-4 font-semibold text-slate-200">
                          {u.name || "Unknown"}
                        </td>
                        <td className="p-4 text-slate-400">
                          {u.email}
                        </td>
                        <td className="p-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                            u.role === "admin" 
                              ? "bg-indigo-500/10 text-indigo-400 border-indigo-500/30" 
                              : "bg-slate-800 text-slate-300 border-slate-700"
                          }`}>
                            {u.role}
                          </span>
                        </td>
                        <td className="p-4 text-right">
                          {u.email !== "tanaymukker@gmail.com" && (
                            <button
                              onClick={() => handleRoleChange(u.email, u.role)}
                              className={`text-xs font-bold px-3 py-1.5 rounded-lg border transition-all ${
                                u.role === "admin"
                                  ? "text-red-400 border-red-500/20 hover:bg-red-500/10"
                                  : "text-indigo-400 border-indigo-500/20 hover:bg-indigo-500/10"
                              }`}
                            >
                              {u.role === "admin" ? "Revoke Admin" : "Make Admin"}
                            </button>
                          )}
                          {u.email === "tanaymukker@gmail.com" && (
                            <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-widest">Protected</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
