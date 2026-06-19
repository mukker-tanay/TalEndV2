import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/router";
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
  name_confidence?: string;
  email?: string;
  phone?: string;
  location?: string;
  current_company?: string;
  company_confidence?: string;
  current_position?: string;
  position_confidence?: string;
  total_experience_years?: number | string;
  experience_confidence?: string;
  last_education?: string;
  graduation_batch?: number;
  skills?: string[];
  match_score: number;
  stored_filename: string;
  original_filename: string;
  upload_time?: string;
};

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState<{ total_matching: number; total_pages: number; has_next: boolean; has_prev: boolean } | null>(null);
  const [sliderOpen, setSliderOpen] = useState(false);
  const [sliderIndex, setSliderIndex] = useState(0);
  const [showFilters, setShowFilters] = useState(false);

  const [batchMin, setBatchMin] = useState(1950);
  const [batchMax, setBatchMax] = useState(2030);
  const [lastEducation, setLastEducation] = useState("");
  const [uploadRange, setUploadRange] = useState<string>("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const [showTagDropdown, setShowTagDropdown] = useState(false);
  const tagDropdownRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/tags`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((data) => { if (Array.isArray(data)) setAvailableTags(data); })
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (tagDropdownRef.current && !tagDropdownRef.current.contains(e.target as Node)) {
        setShowTagDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const fetchResults = async (pageNum: number) => {
    setLoading(true);
    if (!token) { setLoading(false); return; }

    const params = new URLSearchParams();
    params.append("query", query);
    params.append("page", pageNum.toString());
    params.append("limit", "50");

    if (selectedTags.length > 0) params.append("tags", selectedTags.join(","));

    if (showFilters) {
      if (batchMin > 1950) params.append("batch_min", batchMin.toString());
      if (batchMax < 2030) params.append("batch_max", batchMax.toString());
      if (lastEducation.trim()) params.append("last_education", lastEducation.trim());
      if (uploadRange.trim()) params.append("upload_range", uploadRange.trim());
    }

    try {
      const res = await fetch(`${API_URL}/search-cvs?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      });
      if (!res.ok) { setLoading(false); return; }
      const data = await res.json();
      setResults(Array.isArray(data.results) ? data.results : []);
      setPagination(data.pagination ?? null);
    } catch (err) {
      console.error("Search error:", err);
    }
    setLoading(false);
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() && selectedTags.length === 0) return;
    setPage(1);
    await fetchResults(1);
  };

  const goToPage = async (pageNum: number) => {
    setPage(pageNum);
    await fetchResults(pageNum);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const closePanel = () => {
    setSliderOpen(false);
    fetchResults(page);
  };

  const openSlider = (cv: SearchResult) => {
    const idx = results.findIndex((item) => item._id === cv._id);
    setSliderIndex(idx);
    setSliderOpen(true);
  };

  const downloadCSV = () => {
    const headers = ["Name", "Email", "Phone"];
    const rows = results.map((cv) => [cv.name || "", cv.email || "", cv.phone || ""]);
    const csv = [headers, ...rows]
      .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "candidates.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const resetFilters = () => {
    setBatchMin(1950);
    setBatchMax(2030);
    setLastEducation("");
    setUploadRange("");
    setSelectedTags([]);
  };

  return (
    <div className="min-h-screen bg-gray-100 text-gray-900">
      <nav className="bg-gray-50 border-b border-gray-200 p-4 flex justify-between items-center sticky top-0 z-10 shadow-sm">
        <div className="text-2xl font-black text-gray-900 tracking-tight">JobNoc</div>
        <div className="space-x-3">
          <button onClick={() => (window.location.href = "/dashboard")} className="text-sm font-semibold text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-all duration-150">Dashboard</button>
          <button onClick={() => (window.location.href = "/profile")} className="text-sm font-semibold text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-all duration-150">Profile</button>
          <button onClick={() => { localStorage.removeItem("token"); window.location.href = "/login"; }} className="text-sm font-semibold text-red-600 hover:text-red-700 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-all duration-150">Sign Out</button>
        </div>
      </nav>

      <div className="px-6 py-10 max-w-6xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-extrabold tracking-tight text-gray-900">CV Sourcing Directory</h1>
          <p className="text-sm text-gray-500 mt-1">Search through parsed candidate profiles sorted by best matching score</p>
        </header>

        <form onSubmit={handleSearch} className="flex flex-col gap-4 mb-8 bg-gray-50 border border-gray-200 p-6 rounded-2xl shadow-sm">
          <div className="flex flex-col gap-2">
            <div className="flex gap-3">
              <input
                type="text"
                placeholder="Search by conversational prompt, keywords, or select tags below..."
                className="flex-grow bg-gray-50 border border-gray-300 rounded-xl px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all text-sm"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button type="submit" className="bg-gray-900 hover:bg-black text-white font-semibold px-6 py-2.5 rounded-xl transition-all shadow-sm text-sm">
                {loading ? "Searching..." : "Search"}
              </button>
            </div>
            <p className="text-[11px] text-gray-500 font-medium px-1">
              Tip: You can use plain English conversational queries. JobNoc AI will automatically translate and filter by experience, skills, and background.
            </p>
          </div>

          {/* Tag filter dropdown — always visible */}
          {availableTags.length > 0 && (
            <div className="relative" ref={tagDropdownRef}>
              <button
                type="button"
                onClick={() => setShowTagDropdown((v) => !v)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-semibold transition-all ${
                  selectedTags.length > 0
                    ? "bg-blue-50 border-blue-300 text-blue-700"
                    : "bg-gray-50 border-gray-300 text-gray-700 hover:bg-gray-100"
                }`}
              >
                <span>Tags</span>
                {selectedTags.length > 0 && (
                  <span className="bg-blue-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                    {selectedTags.length}
                  </span>
                )}
                <span className="text-gray-400 text-xs">{showTagDropdown ? "▲" : "▼"}</span>
              </button>

              {showTagDropdown && (
                <div className="absolute top-full left-0 mt-1 z-20 bg-white border border-gray-200 rounded-xl shadow-lg p-3 min-w-[200px] max-h-60 overflow-y-auto">
                  {availableTags.map((tag) => (
                    <label key={tag} className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-gray-50 cursor-pointer text-sm text-gray-700 font-medium">
                      <input
                        type="checkbox"
                        checked={selectedTags.includes(tag)}
                        onChange={() => toggleTag(tag)}
                        className="accent-blue-600 w-3.5 h-3.5"
                      />
                      {tag}
                    </label>
                  ))}
                  {selectedTags.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSelectedTags([])}
                      className="mt-2 w-full text-center text-xs text-red-500 hover:text-red-600 font-semibold pt-2 border-t border-gray-100"
                    >
                      Clear Tags
                    </button>
                  )}
                </div>
              )}

              {selectedTags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {selectedTags.map((tag) => (
                    <span key={tag} className="inline-flex items-center bg-blue-50 border border-blue-200 text-blue-700 px-2.5 py-0.5 rounded-md text-xs font-semibold">
                      {tag}
                      <button type="button" onClick={() => toggleTag(tag)} className="ml-1.5 text-blue-400 hover:text-red-500 font-bold">×</button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Filter toggle */}
          <div className="flex items-center justify-between border-t border-gray-200 pt-4 mt-2">
            <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">Search Filters</span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setShowFilters(!showFilters)}
                className="text-blue-600 hover:text-blue-700 flex items-center gap-1.5 text-xs font-semibold"
              >
                <FaFilter className="text-[10px]" />
                {showFilters ? "Hide Filters" : "Show Filters"}
              </button>
              {showFilters && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="text-gray-500 hover:text-gray-700 text-xs font-bold"
                >
                  Reset All
                </button>
              )}
            </div>
          </div>

          {/* Filters section */}
          {showFilters && (
            <div className="flex flex-wrap gap-6 items-start mt-2 p-5 bg-gray-100 rounded-xl border border-gray-200">
              {/* Batch slider */}
              <div className="flex flex-col w-full max-w-sm">
                <label className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">Graduation Batch Year</label>
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
                  trackStyle={[{ backgroundColor: "#2563eb" }]}
                  handleStyle={[
                    { borderColor: "#2563eb", backgroundColor: "#1d4ed8" },
                    { borderColor: "#2563eb", backgroundColor: "#1d4ed8" },
                  ]}
                  railStyle={{ backgroundColor: "#e5e7eb" }}
                  style={{ width: "100%", marginTop: "0.5rem" }}
                />
                <div className="flex justify-between text-xs text-gray-600 mt-2 font-semibold">
                  <span>{batchMin}</span>
                  <span>{batchMax}</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {batchMin === 1950 && batchMax === 2030
                    ? "All years (no active filter)"
                    : `Filtering: ${batchMin} - ${batchMax}`}
                </div>
              </div>

              {/* Last education */}
              <div className="flex flex-col">
                <label className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">Last Education</label>
                <input
                  type="text"
                  placeholder="e.g., B.Tech, MBA"
                  value={lastEducation}
                  onChange={(e) => setLastEducation(e.target.value)}
                  className="bg-gray-50 border border-gray-300 rounded-lg px-3 py-1.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 text-xs transition-all"
                />
                <div className="text-xs text-gray-500 mt-1">
                  {lastEducation.trim() ? `Filter: ${lastEducation}` : "No active filter"}
                </div>
              </div>

              {/* Upload date range */}
              <div className="flex flex-col">
                <label className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">Uploaded Timeline</label>
                <div className="flex flex-wrap gap-2.5">
                  {[
                    { label: "Within 1 month", value: "1m" },
                    { label: "Within 3 months", value: "3m" },
                    { label: "Within 6 months", value: "6m" },
                    { label: "Within 1 year", value: "1y" },
                    { label: "Within 2 years", value: "2y" },
                    { label: "2+ years ago", value: "2y+" },
                  ].map((opt) => (
                    <label key={opt.value} className="flex items-center gap-1.5 text-xs text-gray-700 font-semibold cursor-pointer">
                      <input
                        type="radio"
                        name="uploadRange"
                        value={opt.value}
                        checked={uploadRange === opt.value}
                        onChange={() => setUploadRange(opt.value)}
                        className="accent-blue-600"
                      />
                      {opt.label}
                    </label>
                  ))}
                  <button
                    type="button"
                    className="text-xs text-blue-600 hover:text-blue-700 hover:underline font-bold"
                    onClick={() => setUploadRange("")}
                    style={{ minWidth: 0 }}
                  >
                    Clear Filter
                  </button>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {uploadRange ? `Filter: ${uploadRange}` : "No active filter"}
                </div>
              </div>
            </div>
          )}

          {/* Show active filters summary */}
          {showFilters && (
            <div className="text-xs text-blue-800 bg-blue-50 border border-blue-200 p-3 rounded-xl font-semibold">
              <strong>Active Sourcing Filters:</strong> {
                [
                  selectedTags.length > 0 ? `Tags: ${selectedTags.join(", ")}` : null,
                  batchMin > 1950 || batchMax < 2030 ? `Batch: ${batchMin}-${batchMax}` : null,
                  lastEducation.trim() ? `Education: ${lastEducation}` : null,
                  uploadRange ? `Uploaded: ${uploadRange}` : null
                ].filter(Boolean).join(" · ") || "None"
              }
            </div>
          )}
        </form>

        {/* Results */}
        {results.length === 0 && !loading && (query || selectedTags.length > 0) && (
          <p className="text-gray-500 text-sm italic">No matching candidate profiles found{query ? ` for "${query}"` : ""}.</p>
        )}
        {results.length === 0 && !loading && !query && selectedTags.length === 0 && (
          <p className="text-gray-500 text-sm italic">Enter keywords or select a tag to browse candidates.</p>
        )}

        {pagination && (
          <div className="mb-4 flex items-center justify-between">
            <span className="text-xs text-gray-500 font-semibold">
              {pagination.total_matching} candidate{pagination.total_matching !== 1 ? "s" : ""} matched · Page {page} of {pagination.total_pages}
            </span>
            {results.length > 0 && (
              <button
                type="button"
                onClick={downloadCSV}
                className="flex items-center gap-2 px-4 py-1.5 bg-gray-900 hover:bg-black text-white text-xs font-semibold rounded-xl shadow-sm transition-all"
              >
                ↓ Download CSV
              </button>
            )}
          </div>
        )}

        <div className="grid gap-6">
          {results.map((cv) => (
            <div key={cv._id} className="bg-gray-50 border border-gray-200 rounded-2xl p-6 shadow-sm relative">
              <div className="absolute top-6 right-6 bg-blue-50 text-blue-700 border border-blue-200 px-3 py-1 rounded-full text-xs font-bold">
                {cv.match_score.toFixed(2)} Match
              </div>
              <div className="mb-4">
                <h2 className="text-xl font-bold text-gray-900">{cv.name || "Parsed Candidate Profile"}</h2>
                <p className="text-sm text-gray-500 mt-1">
                  {cv.email || "No Email Sourced"} | {cv.phone || "No Phone Sourced"}
                </p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 border-t border-gray-200 pt-4">
                <div><span className="text-gray-500 font-bold uppercase text-[10px] tracking-wider block">Current Employer</span> <span className="font-semibold text-gray-900 text-sm">{cv.current_company || "N/A"}</span></div>
                <div><span className="text-gray-500 font-bold uppercase text-[10px] tracking-wider block">Designation</span> <span className="font-semibold text-gray-900 text-sm">{cv.current_position || "N/A"}</span></div>
                <div><span className="text-gray-500 font-bold uppercase text-[10px] tracking-wider block">Last Education</span> <span className="font-semibold text-gray-900 text-sm">{cv.last_education || "N/A"}</span></div>
                <div><span className="text-gray-500 font-bold uppercase text-[10px] tracking-wider block">Graduation Batch</span> <span className="font-semibold text-gray-900 text-sm">{cv.graduation_batch || "N/A"}</span></div>
              </div>
              
              {cv.skills && cv.skills.length > 0 && (
                <div className="mt-4 border-t border-gray-200 pt-4">
                  <span className="text-gray-500 font-bold uppercase text-[10px] tracking-wider block mb-2">Sourced Skills</span>
                  <div className="flex flex-wrap gap-1.5">
                    {cv.skills.map((skill, idx) => (
                      <span key={idx} className="bg-gray-100 border border-gray-200 text-gray-700 px-2.5 py-1 rounded-md text-[11px] font-semibold">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Direct Recruiter Actions */}
              <div className="flex flex-wrap items-center gap-3 mt-6 pt-5 border-t border-gray-200">
                {cv.email && (
                  <a
                    href={`mailto:${cv.email}`}
                    className="px-4 py-2 rounded-xl bg-gray-900 hover:bg-black text-white text-xs font-semibold shadow-sm transition-all"
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
                      className="px-4 py-2 rounded-xl bg-green-600 hover:bg-green-700 text-white text-xs font-semibold shadow-sm transition-all"
                    >
                      WhatsApp Sourcing
                    </a>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(cv.phone!);
                        alert("Phone number copied to clipboard");
                      }}
                      className="px-4 py-2 rounded-xl bg-gray-50 border border-gray-300 hover:bg-gray-100 text-gray-700 text-xs font-semibold transition-all"
                    >
                      Copy Mobile Number
                    </button>
                  </>
                )}
                <button 
                  onClick={() => openSlider(cv)} 
                  className="px-4 py-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 hover:text-blue-800 text-xs font-bold transition-all ml-auto"
                >
                  Open PDF Document
                </button>
              </div>

              {cv.upload_time && (
                <div className="absolute bottom-3 right-6 text-[10px] text-gray-400 font-bold uppercase tracking-wider">
                  Uploaded: {new Date(cv.upload_time).toLocaleDateString()}
                </div>
              )}
            </div>
          ))}
        </div>

        {pagination && pagination.total_pages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-8">
            <button
              onClick={() => goToPage(page - 1)}
              disabled={!pagination.has_prev || loading}
              className="px-4 py-2 rounded-xl bg-white border border-gray-300 text-gray-700 text-xs font-semibold disabled:opacity-30 hover:bg-gray-50 transition-all"
            >
              Previous
            </button>
            <span className="text-xs text-gray-500 font-bold px-3">
              {page} / {pagination.total_pages}
            </span>
            <button
              onClick={() => goToPage(page + 1)}
              disabled={!pagination.has_next || loading}
              className="px-4 py-2 rounded-xl bg-white border border-gray-300 text-gray-700 text-xs font-semibold disabled:opacity-30 hover:bg-gray-50 transition-all"
            >
              Next
            </button>
          </div>
        )}
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