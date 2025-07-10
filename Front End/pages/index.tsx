import { useRouter } from 'next/router'

export default function Home() {
  const router = useRouter()

  return (
    <div className="flex items-center justify-center h-screen bg-gray-100">
      <div className="bg-white p-8 rounded shadow-md w-96 text-center">
        <h1 className="text-2xl font-bold mb-6">Welcome to Talend UI</h1>
        <button
          onClick={() => router.push('/login')}
          className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600"
        >
          Login
        </button>
        <p className="mt-4 text-sm">
          New user?{' '}
          <a href="/register" className="text-blue-600 hover:underline">
            Register now!
          </a>
        </p>
      </div>
    </div>
  )
}
