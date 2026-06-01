import { useRouter } from 'next/router'

export default function Home() {
  const router = useRouter()

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100 px-4">
      <div className="bg-gray-50 p-8 rounded-2xl border border-gray-200 shadow-sm w-full max-w-md text-center transition-all duration-300">
        <div className="mb-8">
          <div className="inline-block px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-bold tracking-wider uppercase mb-3">
            Internal Portal
          </div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">JobNoc</h1>
          <p className="mt-2 text-sm text-gray-500">Consultancy Sourcing Command Center</p>
        </div>
        
        <button
          onClick={() => router.push('/login')}
          className="w-full bg-gray-900 hover:bg-black text-white font-semibold py-2.5 rounded-xl shadow-sm transition-all duration-200"
        >
          Sign In
        </button>
      </div>
    </div>
  )
}

