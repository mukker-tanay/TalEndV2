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
  const [newRole, setNewRole] = useState("user");
  const [createMsg, setCreateMsg] = useState("");
  
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const role = typeof window !== "undefined" ? localStorage.getItem("role") : null;

  useEffect(() => {
    const requirePassChange = typeof window !== "undefined" ? localStorage.getItem("require_password_change") : null;
    
    if (!token) {
      router.push("/login");
    } else if (requirePassChange) {
      router.push("/change-password");
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
          role: newRole,
        }),
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to create user");
      
      setCreateMsg("User created successfully!");
      setNewName("");
      setNewEmail("");
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

  if (loading) return <div className="h-screen bg-gray-50 text-gray-500 flex items-center justify-center font-semibold">Loading Admin Panel...</div>;

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 p-6 flex flex-col justify-between">
        <div>
          <div className="mb-10 px-2">
            <h1 className="text-2xl font-black text-gray-900 tracking-tight">JobNoc</h1>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold mt-1">Super Admin</p>
          </div>
          
          <nav className="space-y-1.5">
            <button
              onClick={() => router.push("/dashboard")}
              className="text-left w-full py-2.5 px-4 rounded-xl text-gray-600 hover:bg-gray-100 hover:text-gray-900 font-semibold transition-all duration-150 text-sm flex items-center gap-3"
            >
              Recruiter Workspace
            </button>
            <button
              className="text-left w-full py-2.5 px-4 rounded-xl text-blue-700 bg-blue-50 font-bold transition-all duration-150 text-sm flex items-center gap-3 border border-blue-100"
            >
              Access Management
            </button>
          </nav>
        </div>

        <button
          onClick={handleLogout}
          className="text-left w-full py-2.5 px-4 text-red-600 hover:bg-red-50 hover:text-red-700 rounded-xl font-semibold transition-all duration-150 text-sm flex items-center gap-3"
        >
          Sign Out
        </button>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-8 lg:p-10">
        <header className="mb-8">
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">Access Management</h1>
          <p className="text-sm text-gray-500 mt-1">Control who can access the recruiter workspace and assign administrative privileges</p>
        </header>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Create User Form */}
          <div className="xl:col-span-1">
            <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm sticky top-8">
              <h2 className="text-lg font-bold text-gray-900 mb-4">Provision New Account</h2>
              
              <form onSubmit={handleCreateUser} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">Full Name</label>
                  <input
                    type="text"
                    required
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="w-full bg-white border border-gray-300 rounded-xl px-4 py-2 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-all text-sm"
                    placeholder="Jane Doe"
                  />
                </div>
                
                <div>
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">Email Address</label>
                  <input
                    type="email"
                    required
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    className="w-full bg-white border border-gray-300 rounded-xl px-4 py-2 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-all text-sm"
                    placeholder="jane@agency.com"
                  />
                </div>
                


                <div>
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">Access Role</label>
                  <select 
                    value={newRole} 
                    onChange={(e) => setNewRole(e.target.value)}
                    className="w-full bg-white border border-gray-300 rounded-xl px-4 py-2 text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-all text-sm appearance-none"
                  >
                    <option value="user">Standard User (Recruiter)</option>
                    <option value="admin">Administrator</option>
                  </select>
                </div>
                
                <button
                  type="submit"
                  className="w-full bg-gray-900 hover:bg-black text-white font-semibold py-2.5 rounded-xl mt-2 shadow-sm transition-all duration-200 text-sm"
                >
                  Create Account
                </button>

                {createMsg && (
                  <div className={`mt-4 p-3 rounded-xl text-xs font-bold border ${createMsg.includes("successfully") ? "bg-green-50 text-green-700 border-green-200" : "bg-red-50 text-red-700 border-red-200"}`}>
                    {createMsg}
                  </div>
                )}
              </form>
            </div>
          </div>

          {/* User Ledger */}
          <div className="xl:col-span-2">
            <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
              <div className="p-5 border-b border-gray-200 flex justify-between items-center bg-gray-50">
                <h2 className="text-lg font-bold text-gray-900">Registered Users Ledger</h2>
                <span className="text-xs font-bold text-gray-600 bg-white px-3 py-1 rounded-full border border-gray-200">
                  {users.length} Total
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse">
                  <thead className="bg-white border-b border-gray-200 text-gray-600 font-bold text-xs tracking-wider uppercase">
                    <tr>
                      <th className="p-4">Name</th>
                      <th className="p-4">Email Address</th>
                      <th className="p-4">Role</th>
                      <th className="p-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {users.map((u, i) => (
                      <tr key={i} className="hover:bg-gray-50 transition-all duration-150">
                        <td className="p-4 font-semibold text-gray-900">
                          {u.name || "Unknown"}
                        </td>
                        <td className="p-4 text-gray-600">
                          {u.email}
                        </td>
                        <td className="p-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                            u.role === "admin" 
                              ? "bg-blue-50 text-blue-700 border-blue-200" 
                              : "bg-gray-100 text-gray-600 border-gray-200"
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
                                  ? "text-red-600 border-red-200 hover:bg-red-50"
                                  : "text-blue-600 border-blue-200 hover:bg-blue-50"
                              }`}
                            >
                              {u.role === "admin" ? "Revoke Admin" : "Make Admin"}
                            </button>
                          )}
                          {u.email === "tanaymukker@gmail.com" && (
                            <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Protected</span>
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
