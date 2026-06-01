import { useState } from "react";
import CVSlider, { CVType } from "../components/CVSlider";
import Slider from "rc-slider";
import { FaFilter } from "react-icons/fa";
// Force production API URL if running on the live domain, ignoring the hardcoded localhost in .env
let API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
if (typeof window !== 'undefined' && window.location.hostname === 'jobnoc.com') {
  API_URL = 'https://jobnoc.com/api';
}
type SearchResult = {
  _id: string;
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  current_company?: string;
  current_position?: string;
  last_education?: string;
  graduation_batch?: number;
  skills?: string[];
  match_score: number;
  stored_filename: string;
  original_filename: string;
  upload_time?: string;
};

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [sliderOpen, setSliderOpen] = useState(false);
  const [sliderIndex, setSliderIndex] = useState(0);
  const [showFilters, setShowFilters] = useState(false);

  const [batchMin, setBatchMin] = useState(1950);
  const [batchMax, setBatchMax] = useState(2030);
  const [lastEducation, setLastEducation] = useState("");
  const [uploadRange, setUploadRange] = useState<string>("");

  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const savedToken = localStorage.getItem("token");
    const requirePassChange = localStorage.getItem("require_password_change");
    setToken(savedToken);

    if (!savedToken) {
      router.push("/login");
    } else if (requirePassChange === "true") {
      router.push("/change-password");
    }
  }, [router]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    if (!token) {
      console.error("No auth token found");
      setLoading(false);
      return;
    }

    const params = new URLSearchParams();
    params.append("query", query);
    
    if (showFilters) {
      if (batchMin > 1950) {
        params.append("batch_min", batchMin.toString());
      }
      if (batchMax < 2030) {
        params.append("batch_max", batchMax.toString());
      }
      
      if (lastEducation.trim()) {
        params.append("last_education", lastEducation.trim());
      }
      
      if (uploadRange.trim()) {
        params.append("upload_range", uploadRange.trim());
      }
    }

    try {
      const res = await fetch(`${API_URL}/search-cvs?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (!res.ok) {
        const errMsg = await res.text();
        console.error("Backend error:", res.status, errMsg);
        setLoading(false);
        return;
      }

      const data = await res.json();
      console.log("Search response:", data);
      setResults(Array.isArray(data.results) ? data.results : []);
    } catch (err) {
      console.error("Search error:", err);
    }

    setLoading(false);
  };

  const closePanel = () => {
    setSliderOpen(false);
  };

  const openSlider = (cv: SearchResult) => {
    const idx = results.findIndex((item) => item._id === cv._id);
    setSliderIndex(idx);
    setSliderOpen(true);
  };

  const resetFilters = () => {
    setBatchMin(1950);
    setBatchMax(2030);
    setLastEducation("");
    setUploadRange("");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <nav className="bg-slate-900 border-b border-slate-800/80 p-4 flex justify-between items-center sticky top-0 z-10 shadow-lg">
        <div className="text-2xl font-black text-indigo-400 tracking-tight">JobNoc</div>
        <div className="space-x-3">
          <button onClick={() => (window.location.href = "/dashboard")} className="text-sm font-semibold text-slate-300 hover:text-slate-100 px-3 py-1.5 rounded-lg hover:bg-slate-800 transition-all duration-150">Dashboard</button>
          <button onClick={() => (window.location.href = "/profile")} className="text-sm font-semibold text-slate-300 hover:text-slate-100 px-3 py-1.5 rounded-lg hover:bg-slate-800 transition-all duration-150">Profile</button>
          <button onClick={() => { localStorage.removeItem("token"); window.location.href = "/login"; }} className="text-sm font-semibold text-red-400 hover:text-red-300 px-3 py-1.5 rounded-lg hover:bg-red-500/10 transition-all duration-150">Sign Out</button>
        </div>
      </nav>

      <div className="px-6 py-10 max-w-6xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-100">CV Sourcing Directory</h1>
          <p className="text-sm text-slate-400 mt-1">Search through parsed candidate profiles sorted by best matching score</p>
        </header>

        <form onSubmit={handleSearch} className="flex flex-col gap-4 mb-8 bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
          <div className="flex flex-col gap-2">
            <div className="flex gap-3">
              <input
                type="text"
                placeholder="Search by conversational prompt (e.g., Python developer with 3 years of experience) or keywords..."
                className="flex-grow bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-all text-sm"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                required
              />
              <button type="submit" className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-6 py-2.5 rounded-xl transition-all shadow-lg shadow-indigo-600/10 text-sm">
                {loading ? "Searching..." : "Search"}
              </button>
            </div>
            <p className="text-[11px] text-slate-500 font-medium px-1">
              Tip: You can use plain English conversational queries. JobNoc AI will automatically translate and filter by experience, skills, and background.
            </p>
          </div>


          {/* Filter toggle */}
          <div className="flex items-center justify-between border-t border-slate-800/80 pt-4 mt-2">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Search Filters</span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setShowFilters(!showFilters)}
                className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1.5 text-xs font-semibold"
              >
                <FaFilter className="text-[10px]" />
                {showFilters ? "Hide Filters" : "Show Filters"}
              </button>
              {showFilters && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="text-slate-500 hover:text-slate-400 text-xs font-semibold"
                >
                  Reset All
                </button>
              )}
            </div>
          </div>

          {/* Filters section */}
          {showFilters && (
            <div className="flex flex-wrap gap-6 items-start mt-2 p-5 bg-slate-950/60 rounded-xl border border-slate-850">
              {/* Batch slider */}
              <div className="flex flex-col w-full max-w-sm">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Graduation Batch Year</label>
                <Slider
                  range
                  min={1950}
                  max={2030}
                  value={[batchMin, batchMax]}
                  onChange={(value: number | [number, number]) => {
                    if (Array.isArray(value)) {
                      const [min, max] = value;
                      setBatchMin(min);
                      setBatchMax(max);
                    }
                  }}
                  allowCross={false}
                  trackStyle={[{ backgroundColor: "#6366f1" }]}
                  handleStyle={[
                    { borderColor: "#6366f1", backgroundColor: "#4f46e5" },
                    { borderColor: "#6366f1", backgroundColor: "#4f46e5" },
                  ]}
                  railStyle={{ backgroundColor: "#1e293b" }}
                  style={{ width: "100%", marginTop: "0.5rem" }}
                />
                <div className="flex justify-between text-xs text-slate-400 mt-2 font-semibold">
                  <span>{batchMin}</span>
                  <span>{batchMax}</span>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {batchMin === 1950 && batchMax === 2030
                    ? "All years (no active filter)"
                    : `Filtering: ${batchMin} - ${batchMax}`}
                </div>
              </div>

              {/* Last education */}
              <div className="flex flex-col">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Last Education</label>
                <input
                  type="text"
                  placeholder="e.g., B.Tech, MBA"
                  value={lastEducation}
                  onChange={(e) => setLastEducation(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 text-xs transition-all"
                />
                <div className="text-xs text-slate-500 mt-1">
                  {lastEducation.trim() ? `Filter: ${lastEducation}` : "No active filter"}
                </div>
              </div>

              {/* Upload date range */}
              <div className="flex flex-col">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Uploaded Timeline</label>
                <div className="flex flex-wrap gap-2.5">
                  {[
                    { label: "Within 1 month", value: "1m" },
                    { label: "Within 3 months", value: "3m" },
                    { label: "Within 6 months", value: "6m" },
                    { label: "Within 1 year", value: "1y" },
                    { label: "Within 2 years", value: "2y" },
                    { label: "2+ years ago", value: "2y+" },
                  ].map((opt) => (
                    <label key={opt.value} className="flex items-center gap-1.5 text-xs text-slate-300 font-semibold cursor-pointer">
                      <input
                        type="radio"
                        name="uploadRange"
                        value={opt.value}
                        checked={uploadRange === opt.value}
                        onChange={() => setUploadRange(opt.value)}
                        className="accent-indigo-500"
                      />
                      {opt.label}
                    </label>
                  ))}
                  <button
                    type="button"
                    className="text-xs text-indigo-400 hover:text-indigo-300 hover:underline font-semibold"
                    onClick={() => setUploadRange("")}
                    style={{ minWidth: 0 }}
                  >
                    Clear Filter
                  </button>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {uploadRange ? `Filter: ${uploadRange}` : "No active filter"}
                </div>
              </div>
            </div>
          )}

          {/* Show active filters summary */}
          {showFilters && (
            <div className="text-xs text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 p-3 rounded-xl font-semibold">
              <strong>Active Sourcing Filters:</strong> {
                [
                  batchMin > 1950 || batchMax < 2030 ? `Batch: ${batchMin}-${batchMax}` : null,
                  lastEducation.trim() ? `Education: ${lastEducation}` : null,
                  uploadRange ? `Uploaded: ${uploadRange}` : null
                ].filter(Boolean).join(", ") || "None"
              }
            </div>
          )}
        </form>

        {/* Results */}
        {results.length === 0 && !loading && query && (
          <p className="text-slate-500 text-sm italic">No matching candidate profiles found in JobNoc database for "{query}".</p>
        )}
        {results.length === 0 && !loading && !query && (
          <p className="text-slate-500 text-sm italic">Enter technical keywords or candidate credentials in the query box above.</p>
        )}

        <div className="grid gap-6">
          {results.map((cv) => (
            <div key={cv._id} className="cv-card relative">
              <div className="cv-badge">{cv.match_score.toFixed(2)} Match</div>
              <div className="mb-4">
                <h2 className="cv-name">{cv.name || "Parsed Candidate Profile"}</h2>
                <p className="cv-meta">
                  {cv.email || "No Email Sourced"} | {cv.phone || "No Phone Sourced"}
                </p>
              </div>
              <div className="cv-info-grid border-t border-slate-800/50 pt-3">
                <div><span className="text-slate-500 font-semibold uppercase text-[10px] tracking-wider block">Current Employer</span> <span className="font-semibold">{cv.current_company || "N/A"}</span></div>
                <div><span className="text-slate-500 font-semibold uppercase text-[10px] tracking-wider block">Designation</span> <span className="font-semibold">{cv.current_position || "N/A"}</span></div>
                <div><span className="text-slate-500 font-semibold uppercase text-[10px] tracking-wider block">Last Education</span> <span className="font-semibold">{cv.last_education || "N/A"}</span></div>
                <div><span className="text-slate-500 font-semibold uppercase text-[10px] tracking-wider block">Graduation Batch</span> <span className="font-semibold">{cv.graduation_batch || "N/A"}</span></div>
              </div>
              
              {cv.skills && cv.skills.length > 0 && (
                <div className="mt-4 border-t border-slate-800/50 pt-3">
                  <span className="text-slate-500 font-semibold uppercase text-[10px] tracking-wider block mb-1.5">Sourced Skills</span>
                  <div className="flex flex-wrap">
                    {cv.skills.map((skill, idx) => (
                      <span key={idx} className="cv-skill-pill">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Direct Recruiter Actions */}
              <div className="flex items-center gap-2 mt-5 pt-4 border-t border-slate-800/80">
                {cv.email && (
                  <a
                    href={`mailto:${cv.email}`}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/10 transition-all"
                  >
                    Email Candidate
                  </a>
                )}
                {cv.phone && (
                  <>
                    <a
                      href={`https://wa.me/${cv.phone.replace(/[^\d]/g, "")}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/10 transition-all"
                    >
                      WhatsApp Sourcing
                    </a>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(cv.phone);
                        alert("Phone number copied to clipboard");
                      }}
                      className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs font-semibold transition-all"
                    >
                      Copy Mobile Number
                    </button>
                  </>
                )}
                <button 
                  onClick={() => openSlider(cv)} 
                  className="px-4 py-2 rounded-xl bg-slate-950 border border-slate-800 text-indigo-400 hover:text-indigo-300 text-xs font-semibold transition-all ml-auto"
                >
                  Open PDF Document
                </button>
              </div>

              {cv.upload_time && (
                <div className="absolute bottom-2 right-4 text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
                  Uploaded: {new Date(cv.upload_time).toLocaleDateString()}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {sliderOpen && (
        <CVSlider
          cvList={results as CVType[]}
          current={sliderIndex}
          setCurrent={setSliderIndex}
          onClose={closePanel}
        />
      )}
    </div>
  );
}