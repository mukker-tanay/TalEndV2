import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import CVSlider, { CVType } from "../components/CVSlider";

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
type UploadedCV = {
  id: string;
  name?: string;
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
  }));
}

export default function Dashboard() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [cvList, setCvList] = useState<UploadedCV[]>([]);
  const [message, setMessage] = useState("");
  const [sliderOpen, setSliderOpen] = useState(false);
  const [sliderIndex, setSliderIndex] = useState(0);
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");

  useEffect(() => {
    if (!token) router.push("/login");
    else fetchCVs();
  }, []);

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
    if (!isZip) formData.append("tags", JSON.stringify(tags));

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
          stored_filename: file.name,
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

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/");
  };

  return (
    <div className="flex h-screen bg-slate-950">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800/80 p-6 flex flex-col justify-between">
        <div>
          <div className="mb-10 px-2">
            <h1 className="text-2xl font-black text-indigo-400 tracking-tight">JobNoc</h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mt-1">Consultancy Admin</p>
          </div>
          
          <nav className="space-y-1.5">
            <button
              onClick={() => router.push("/search")}
              className="text-left w-full py-2.5 px-4 rounded-xl text-slate-300 hover:bg-slate-800 hover:text-slate-100 font-semibold transition-all duration-150 text-sm flex items-center gap-3"
            >
              Search Database
            </button>
            <button
              onClick={() => alert("Profile configurations are not active")}
              className="text-left w-full py-2.5 px-4 rounded-xl text-slate-300 hover:bg-slate-800 hover:text-slate-100 font-semibold transition-all duration-150 text-sm flex items-center gap-3"
            >
              Profile Settings
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
          <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight">Recruiter Workspace</h1>
          <p className="text-sm text-slate-400 mt-1">Easily store and manage parsed resumes inside your proprietary pool</p>
        </header>

        {/* Uploader Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 mb-8 max-w-2xl">
          <form onSubmit={handleUpload}>
            <label className="block mb-2 text-sm font-semibold text-slate-300 uppercase tracking-wider">Upload Candidate CV (PDF, DOCX, or ZIP)</label>
            <div className="border-2 border-dashed border-slate-800 hover:border-indigo-500/40 rounded-xl p-6 text-center transition-all duration-200 bg-slate-950/40">
              <input
                type="file"
                accept=".pdf,.doc,.docx,.zip"
                className="block w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-300 hover:file:bg-slate-700 cursor-pointer"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required
              />
            </div>

            {/* Show tags only if not zip */}
            {file && !file.name.endsWith(".zip") && (
              <div className="mt-4">
                <label className="block mb-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider">Classification Tags</label>
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagInput}
                  placeholder="Type a tag and press Enter to save"
                  className="block w-full bg-slate-950/80 border border-slate-800 rounded-xl px-4 py-2 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-all"
                />
                <div className="flex flex-wrap mt-2.5 gap-1.5">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center bg-indigo-500/10 border border-indigo-500/25 text-indigo-400 px-2.5 py-0.5 rounded-md text-xs font-medium"
                    >
                      {tag}
                      <button
                        type="button"
                        className="ml-2 text-indigo-400 hover:text-red-400 font-bold"
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
              <button type="submit" className="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2 rounded-xl font-semibold shadow-lg shadow-indigo-600/10 transition-all duration-200">
                Parse Resume
              </button>
              {message && (
                <span className="text-xs font-medium text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700/50">
                  {message}
                </span>
              )}
            </div>
          </form>
        </div>

        {/* High-Density Ledger Table */}
        <div className="mb-4">
          <h2 className="text-xl font-bold text-slate-100 tracking-tight">Sourced Candidate Ledger</h2>
          <p className="text-xs text-slate-400 mt-0.5">List of all parsed candidates sorted by upload timeline</p>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden max-w-4xl shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left border-collapse">
              <thead className="bg-slate-800/60 border-b border-slate-800 text-slate-300 font-semibold text-xs tracking-wider uppercase">
                <tr>
                  <th className="p-4">Candidate Name</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Tags</th>
                  <th className="p-4">Sourcing Date</th>
                  <th className="p-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850">
                {cvList.map((cv) => (
                  <tr key={cv.id} className="hover:bg-slate-800/20 transition-all duration-150">
                    <td className="p-4 font-semibold text-slate-200">
                      {cv.name || <span className="text-slate-500 font-normal italic">Name pending parsing</span>}
                    </td>
                    <td className="p-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                        cv.status === "completed" 
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/25" 
                          : cv.status === "error" 
                          ? "bg-red-500/10 text-red-400 border border-red-500/25" 
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/25"
                      }`}>
                        {cv.status}
                      </span>
                    </td>
                    <td className="p-4">
                      {cv.tags && cv.tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {cv.tags.map((tag) => (
                            <span key={tag} className="bg-slate-850 text-slate-300 border border-slate-800 px-2 py-0.5 rounded-md text-[10px] font-semibold">
                              {tag}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-slate-500 text-xs">No tags</span>
                      )}
                    </td>
                    <td className="p-4 text-slate-400 text-xs">
                      {new Date(cv.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="p-4 text-right">
                      <button 
                        onClick={() => openSlider(cv)} 
                        className="text-indigo-400 hover:text-indigo-300 font-semibold hover:underline text-xs"
                      >
                        Open Profile
                      </button>
                    </td>
                  </tr>
                ))}
                {cvList.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-slate-500 italic">
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

