import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import CVSlider, { CVType } from "../components/CVSlider";

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
      const res = await fetch(`http://localhost:8000/list-cvs`, {
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
        const res = await fetch(`http://localhost:8000/cv-status/${cv_id}`, {
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
        isZip ? `http://localhost:8000/upload-zip` : `http://localhost:8000/upload-cv`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        }
      );

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");

      if (isZip) {
        setMessage(`✅ ZIP uploaded! ${data.uploaded?.length || 0} CVs parsing...`);
        setFile(null);
        fetchCVs();
        return;
      }

      // Single file upload logic
      setMessage("✅ Upload successful! Parsing in background...");
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
          setMessage("✅ Parsing complete!");
          fetchCVs();
        } else if (status === "error") {
          setMessage("❌ Parsing failed: " + (error || "Unknown error"));
        }
      });
    } catch (err: any) {
      console.error(err);
      setMessage("❌ Upload failed.");
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
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r p-4 flex flex-col">
        <h1 className="text-xl font-bold mb-8">Talend</h1>
        <button
          onClick={() => router.push("/search")}
          className="text-left w-full mb-2 py-2 px-4 rounded hover:bg-blue-100"
        >
          🔍 Search
        </button>
        <button
          onClick={() => alert("Profile page not implemented yet")}
          className="text-left w-full mb-2 py-2 px-4 rounded hover:bg-blue-100"
        >
          👤 Profile
        </button>
        <button
          onClick={handleLogout}
          className="text-left w-full mt-auto py-2 px-4 text-red-600 hover:bg-red-100 rounded"
        >
          🚪 Logout
        </button>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
        <h1 className="text-3xl font-bold mb-6">Welcome Tanay!</h1>

        <form onSubmit={handleUpload} className="bg-white p-6 rounded shadow-md mb-8 max-w-lg">
          <label className="block mb-2 font-medium">Upload CV (.pdf, .docx or .zip)</label>
          <input
            type="file"
            accept=".pdf,.doc,.docx,.zip"
            className="mb-4"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            required
          />

          {/* Show tags only if not zip */}
          {file && !file.name.endsWith(".zip") && (
            <div className="mb-4">
              <label className="block mb-1 font-medium">Tags</label>
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleTagInput}
                placeholder="Type a tag and press Enter"
                className="block w-full border border-gray-300 p-2"
              />
              <div className="flex flex-wrap mt-2 gap-2">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-sm"
                  >
                    {tag}
                    <button
                      type="button"
                      className="ml-2 text-blue-500 hover:text-red-500"
                      onClick={() => removeTag(tag)}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
            Upload
          </button>
          {message && <p className="mt-4 text-sm">{message}</p>}
        </form>

        <h2 className="text-xl font-semibold mb-2">Uploaded CVs</h2>
        <div className="bg-white shadow-md rounded overflow-x-auto max-w-3xl">
          <table className="w-full text-sm text-left border-collapse">
            <thead className="bg-gray-200">
              <tr>
                <th className="p-3 border-b">Name</th>
                <th className="p-3 border-b">Status</th>
                <th className="p-3 border-b">Tags</th>
                <th className="p-3 border-b">Upload Date</th>
                <th className="p-3 border-b">Action</th>
              </tr>
            </thead>
            <tbody>
              {cvList.map((cv) => (
                <tr key={cv.id} className="border-t">
                  <td className="p-3">{cv.name || <span className="text-gray-400">(No name found)</span>}</td>
                  <td className="p-3">{cv.status}</td>
                  <td className="p-3">
                    {cv.tags && cv.tags.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {cv.tags.map((tag) => (
                          <span key={tag} className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full text-xs">
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-gray-400">No tags</span>
                    )}
                  </td>
                  <td className="p-3">{new Date(cv.uploaded_at).toLocaleString()}</td>
                  <td className="p-3">
                    <button onClick={() => openSlider(cv)} className="text-blue-600 hover:underline">
                      View
                    </button>
                  </td>
                </tr>
              ))}
              {cvList.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-4 text-center text-gray-500">
                    No CVs uploaded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
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
