import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import CVSlider, { CVType } from "../components/CVSlider";

// Force production API URL if running on the live domain, ignoring the hardcoded localhost in .env
let API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
if (typeof window !== 'undefined' && window.location.hostname === 'jobnoc.com') {
  API_URL = 'https://jobnoc.com/api';
}
type UploadedCV = {
  id: string;
  name?: string;
  name_confidence?: string;
  current_company?: string;
  company_confidence?: string;
  current_position?: string;
  position_confidence?: string;
  total_experience_years?: number | string;
  experience_confidence?: string;
  filename: string;
  stored_filename: string;
  uploaded_at: string;
  status: string;
  tags?: string[];
  error?: string;
};

function uploadedCVsToCVTypes(cvList: UploadedCV[]): CVType[] {
  return cvList.map((cv) => ({
    _id: cv.id,
    original_filename: cv.filename,
    stored_filename: cv.stored_filename,
    name: cv.name,
    name_confidence: cv.name_confidence,
    current_company: cv.current_company,
    company_confidence: cv.company_confidence,
    current_position: cv.current_position,
    position_confidence: cv.position_confidence,
    total_experience_years: cv.total_experience_years,
    experience_confidence: cv.experience_confidence,
  }));
}

export default function Dashboard() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [cvList, setCvList] = useState<UploadedCV[]>([]);
  const [message, setMessage] = useState("");
  const [sliderOpen, setSliderOpen] = useState(false);
  const [sliderIndex, setSliderIndex] = useState(0);
  
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    const savedToken = localStorage.getItem("token");
    const savedRole = localStorage.getItem("role");
    const requirePassChange = localStorage.getItem("require_password_change");
    setToken(savedToken);
    setRole(savedRole);

    if (!savedToken) {
      router.push("/login");
    } else if (requirePassChange) {
      router.push("/change-password");
    } else {
      fetchCVs();
    }
  }, []);

  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [editingTagsCvId, setEditingTagsCvId] = useState<string | null>(null);
  const [editTagInput, setEditTagInput] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);

  useEffect(() => {
    if (token) {
      fetchCVs();
    }
  }, [token]);

  // Auto-refresh while any CV is still parsing (uploaded) or completed but nameless
  useEffect(() => {
    const needsRefresh = cvList.some((cv) => cv.status === "uploaded" || !cv.name);
    if (!needsRefresh) return;
    const timer = setTimeout(fetchCVs, 8000);
    return () => clearTimeout(timer);
  }, [cvList]);

  const fetchCVs = async () => {
    try {
      const res = await fetch(`${API_URL}/list-cvs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (Array.isArray(data)) setCvList(data);
    } catch (error) {
      console.error("Failed to fetch CVs", error);
    }
  };

  const pollStatus = async (cv_id: string, onUpdate: (status: string, error?: string) => void) => {
    let attempts = 0;
    const maxAttempts = 30;
    const interval = 2000;
    let done = false;

    while (!done && attempts < maxAttempts) {
      await new Promise((res) => setTimeout(res, interval));
      try {
        const res = await fetch(`${API_URL}/cv-status/${cv_id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (data.status === "completed" || data.status === "error") {
          onUpdate(data.status, data.error);
          done = true;
        } else {
          onUpdate(data.status);
        }
      } catch {}
      attempts++;
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    const isZip = file.name.endsWith(".zip");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tags", JSON.stringify(tags));

    try {
      const res = await fetch(
        isZip ? `${API_URL}/upload-zip` : `${API_URL}/upload-cv`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        }
      );

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");

      if (isZip) {
        setMessage(`ZIP uploaded successfully, ${data.uploaded?.length || 0} candidates parsing in background.`);
        setFile(null);
        setTags([]);
        fetchCVs();
        return;
      }

      setMessage("Upload successful, parsing resume file in background...");
      setFile(null);
      setTags([]);
      setCvList((prev) => [
        {
          id: data.cv_id,
          name: undefined,
          filename: file.name,
          stored_filename: data.stored_filename || file.name,
          uploaded_at: new Date().toISOString(),
          status: "uploaded",
          tags: [...tags],
        },
        ...prev,
      ]);

      pollStatus(data.cv_id, (status, error) => {
        setCvList((prev) =>
          prev.map((cv) =>
            cv.id === data.cv_id ? { ...cv, status, error } : cv
          )
        );
        if (status === "completed") {
          setMessage("Parsing complete.");
          fetchCVs();
        } else if (status === "error") {
          setMessage("Parsing failed: " + (error || "Unknown error"));
        }
      });
    } catch (err: any) {
      console.error(err);
      setMessage("Upload failed.");
    }
  };

  const openSlider = (cv: UploadedCV) => {
    const idx = cvList.findIndex((item) => item.id === cv.id);
    setSliderIndex(idx);
    setSliderOpen(true);
  };

  const handleTagInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && tagInput.trim()) {
      e.preventDefault();
      if (!tags.includes(tagInput.trim())) {
        setTags([...tags, tagInput.trim()]);
      }
      setTagInput("");
    }
  };

  const removeTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  const startEditingTags = (cv: UploadedCV) => {
    setEditingTagsCvId(cv.id);
    setEditTags(cv.tags ? [...cv.tags] : []);
    setEditTagInput("");
  };

  const handleEditTagKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && editTagInput.trim()) {
      e.preventDefault();
      if (!editTags.includes(editTagInput.trim())) {
        setEditTags([...editTags, editTagInput.trim()]);
      }
      setEditTagInput("");
    }
  };

  const saveTagsForCv = async (cvId: string) => {
    try {
      const res = await fetch(`${API_URL}/cv/${cvId}/tags`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(editTags),
      });
      if (!res.ok) throw new Error("Failed to update tags");
      setCvList((prev) =>
        prev.map((cv) => (cv.id === cvId ? { ...cv, tags: [...editTags] } : cv))
      );
      setEditingTagsCvId(null);
    } catch {
      setMessage("Failed to save tags.");
    }
  };

  const reparseStuck = async () => {
    try {
      const res = await fetch(`${API_URL}/reparse-stuck`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setMessage(data.message || "Re-parse triggered.");
      setTimeout(fetchCVs, 5000);
    } catch {
      setMessage("Failed to trigger re-parse.");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/");
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-50 border-r border-gray-200 p-6 flex flex-col justify-between">
        <div>
          <div className="mb-10 px-2">
            <h1 className="text-2xl font-black text-gray-900 tracking-tight">JobNoc</h1>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold mt-1">Consultancy Admin</p>
          </div>
          
          <nav className="space-y-1.5">
            <button
              onClick={() => router.push("/search")}
              className="text-left w-full py-2.5 px-4 rounded-xl text-gray-600 hover:bg-gray-100 hover:text-gray-900 font-semibold transition-all duration-150 text-sm flex items-center gap-3"
            >
              Search Database
            </button>
            <button
              onClick={() => alert("Profile configurations are not active")}
              className="text-left w-full py-2.5 px-4 rounded-xl text-gray-600 hover:bg-gray-100 hover:text-gray-900 font-semibold transition-all duration-150 text-sm flex items-center gap-3"
            >
              Profile Settings
            </button>
            {role === "admin" && (
              <button
                onClick={() => router.push("/admin")}
                className="text-left w-full py-2.5 px-4 rounded-xl text-blue-700 bg-blue-50 hover:bg-blue-100 hover:text-blue-800 font-bold transition-all duration-150 text-sm flex items-center gap-3 border border-blue-100"
              >
                Admin Panel
              </button>
            )}
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
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">Recruiter Workspace</h1>
          <p className="text-sm text-gray-500 mt-1">Easily store and manage parsed resumes inside your proprietary pool</p>
        </header>

        {/* Uploader Card */}
        <div className="bg-gray-50 border border-gray-200 rounded-2xl p-6 mb-8 max-w-2xl shadow-sm">
          <form onSubmit={handleUpload}>
            <label className="block mb-2 text-sm font-bold text-gray-700 uppercase tracking-wider">Upload Candidate CV (PDF, DOCX, or ZIP)</label>
            <div className="border-2 border-dashed border-gray-300 hover:border-gray-400 rounded-xl p-6 text-center transition-all duration-200 bg-gray-50">
              <input
                type="file"
                accept=".pdf,.doc,.docx,.zip"
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-gray-200 file:text-gray-700 hover:file:bg-gray-300 cursor-pointer"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required
              />
            </div>

            {file && (
              <div className="mt-4">
                <label className="block mb-1.5 text-xs font-bold text-gray-700 uppercase tracking-wider">
                  Classification Tags
                  {file.name.endsWith(".zip") && (
                    <span className="ml-2 text-gray-400 font-normal normal-case">— applied to all CVs in this ZIP</span>
                  )}
                </label>
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagInput}
                  placeholder="Type a tag and press Enter to save"
                  className="block w-full bg-gray-50 border border-gray-300 rounded-xl px-4 py-2 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 transition-all"
                />
                <div className="flex flex-wrap mt-2.5 gap-1.5">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center bg-gray-100 border border-gray-200 text-gray-700 px-2.5 py-0.5 rounded-md text-xs font-medium"
                    >
                      {tag}
                      <button
                        type="button"
                        className="ml-2 text-gray-400 hover:text-red-500 font-bold"
                        onClick={() => removeTag(tag)}
                      >
                        x
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-4 mt-6">
              <button type="submit" className="bg-gray-900 hover:bg-black text-white px-5 py-2 rounded-xl font-semibold shadow-sm transition-all duration-200">
                Parse Resume
              </button>
              {message && (
                <span className="text-xs font-medium text-gray-600 bg-gray-100 px-3 py-1.5 rounded-lg border border-gray-200">
                  {message}
                </span>
              )}
            </div>
          </form>
        </div>

        {/* High-Density Ledger Table */}
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900 tracking-tight">Sourced Candidate Ledger</h2>
            <p className="text-xs text-gray-500 mt-0.5">List of all parsed candidates sorted by upload timeline</p>
          </div>
          {cvList.some((cv) => cv.status === "uploaded" || !cv.name) && (
            <button
              type="button"
              onClick={reparseStuck}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-yellow-50 border border-yellow-300 text-yellow-700 hover:bg-yellow-100 transition-all"
            >
              Re-parse pending CVs
            </button>
          )}
        </div>

        <div className="bg-gray-50 border border-gray-200 rounded-2xl overflow-hidden max-w-4xl shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left border-collapse">
              <thead className="bg-gray-100 border-b border-gray-200 text-gray-600 font-semibold text-xs tracking-wider uppercase">
                <tr>
                  <th className="p-4">Candidate Name</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Tags</th>
                  <th className="p-4">Sourcing Date</th>
                  <th className="p-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {cvList.map((cv) => (
                  <tr key={cv.id} className="hover:bg-gray-100 transition-all duration-150">
                    <td className="p-4 text-gray-900">
                      <div className="font-semibold flex items-center flex-wrap gap-1">
                        {cv.name || <span className="text-gray-400 font-normal italic">Name pending parsing</span>}
                        {cv.name && (cv.name_confidence === "medium" || cv.name_confidence === "low") && (
                          <span
                            title="Low-confidence name — please verify"
                            className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700 border border-amber-200"
                          >
                            verify
                          </span>
                        )}
                      </div>
                      {cv.name && (cv.current_position || cv.current_company || (cv.total_experience_years !== undefined && cv.total_experience_years !== null)) && (
                        <div className="text-xs text-gray-500 font-normal mt-1 flex items-center gap-1.5 flex-wrap">
                          <span>
                            {[
                              cv.current_position,
                              cv.current_company,
                              (cv.total_experience_years !== undefined && cv.total_experience_years !== null) ? `${cv.total_experience_years} y` : null
                            ].filter(Boolean).join(" · ")}
                          </span>
                          {((cv.current_company && (cv.company_confidence === "medium" || cv.company_confidence === "low")) ||
                            (cv.current_position && (cv.position_confidence === "medium" || cv.position_confidence === "low")) ||
                            (cv.total_experience_years !== undefined && cv.total_experience_years !== null && (cv.experience_confidence === "medium" || cv.experience_confidence === "low"))) && (
                            <span
                              title={`Low confidence in: ${
                                [
                                  (cv.company_confidence === "medium" || cv.company_confidence === "low") ? "company" : "",
                                  (cv.position_confidence === "medium" || cv.position_confidence === "low") ? "position" : "",
                                  (cv.experience_confidence === "medium" || cv.experience_confidence === "low") ? "experience" : ""
                                ].filter(Boolean).join(", ")
                              }`}
                              className="inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-medium bg-amber-100 text-amber-700 border border-amber-200"
                            >
                              verify details
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="p-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                        cv.status === "completed" 
                          ? "bg-green-100 text-green-700 border border-green-200" 
                          : cv.status === "error" 
                          ? "bg-red-100 text-red-700 border border-red-200" 
                          : "bg-yellow-100 text-yellow-700 border border-yellow-200"
                      }`}>
                        {cv.status}
                      </span>
                    </td>
                    <td className="p-4">
                      {editingTagsCvId === cv.id ? (
                        <div className="flex flex-col gap-1.5 min-w-[200px]">
                          <div className="flex flex-wrap gap-1">
                            {editTags.map((tag) => (
                              <span key={tag} className="inline-flex items-center bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded-md text-[10px] font-bold">
                                {tag}
                                <button
                                  type="button"
                                  className="ml-1.5 text-blue-400 hover:text-red-500 font-bold"
                                  onClick={() => setEditTags(editTags.filter((t) => t !== tag))}
                                >
                                  x
                                </button>
                              </span>
                            ))}
                          </div>
                          <input
                            type="text"
                            value={editTagInput}
                            autoFocus
                            onChange={(e) => setEditTagInput(e.target.value)}
                            onKeyDown={handleEditTagKeyDown}
                            placeholder="Add tag + Enter"
                            className="border border-gray-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
                          />
                          <div className="flex gap-1.5">
                            <button
                              type="button"
                              onClick={() => saveTagsForCv(cv.id)}
                              className="text-[10px] font-semibold bg-gray-900 text-white px-2.5 py-0.5 rounded-md hover:bg-black"
                            >
                              Save
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingTagsCvId(null)}
                              className="text-[10px] font-semibold text-gray-500 hover:text-gray-700"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-wrap gap-1 items-center group">
                          {cv.tags && cv.tags.length > 0 ? (
                            cv.tags.map((tag) => (
                              <span key={tag} className="bg-gray-100 text-gray-700 border border-gray-200 px-2 py-0.5 rounded-md text-[10px] font-bold">
                                {tag}
                              </span>
                            ))
                          ) : (
                            <span className="text-gray-400 text-xs">No tags</span>
                          )}
                          <button
                            type="button"
                            onClick={() => startEditingTags(cv)}
                            className="ml-1 text-gray-300 hover:text-blue-500 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Edit tags"
                          >
                            ✎
                          </button>
                        </div>
                      )}
                    </td>
                    <td className="p-4 text-gray-500 text-xs">
                      {new Date(cv.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="p-4 text-right">
                      <button 
                        onClick={() => openSlider(cv)} 
                        className="text-blue-600 hover:text-blue-700 font-semibold hover:underline text-xs"
                      >
                        Open Profile
                      </button>
                    </td>
                  </tr>
                ))}
                {cvList.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-gray-500 italic">
                      No CV files parsed yet. Drag and drop a file above to begin.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {sliderOpen && (
        <CVSlider
          cvList={uploadedCVsToCVTypes(cvList)}
          current={sliderIndex}
          setCurrent={setSliderIndex}
          onClose={() => setSliderOpen(false)}
        />
      )}
    </div>
  );
}

