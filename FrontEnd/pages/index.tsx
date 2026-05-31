import { useRouter } from 'next/router'

export default function Home() {
  const router = useRouter()

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-950 px-4">
      <div className="bg-slate-900/60 backdrop-blur-md p-8 rounded-2xl border border-slate-800 shadow-2xl w-full max-w-md text-center transition-all duration-300 hover:border-slate-700/80">
        <div className="mb-8">
          <div className="inline-block px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-400 text-xs font-semibold tracking-wider uppercase mb-3">
            Internal Portal
          </div>
          <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight">JobNoc</h1>
          <p className="mt-2 text-sm text-slate-400">Consultancy Sourcing Command Center</p>
        </div>
        
        <button
          onClick={() => router.push('/login')}
          className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-xl shadow-lg shadow-indigo-600/20 hover:shadow-indigo-500/30 transition-all duration-200"
        >
          Sign In
        </button>
        
        <p className="mt-6 text-sm text-slate-400">
          Need an internal account?{' '}
          <a href="/register" className="text-indigo-400 hover:text-indigo-300 font-medium hover:underline">
            Register recruiter
          </a>
        </p>
      </div>
    </div>
  )
}

