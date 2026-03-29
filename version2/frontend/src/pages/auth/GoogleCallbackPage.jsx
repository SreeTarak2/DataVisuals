import { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '@/store/authStore';
import { Loader2 } from 'lucide-react';

export default function GoogleCallbackPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { setGoogleToken } = useAuth();

    useEffect(() => {
        const token = searchParams.get('token');
        const type = searchParams.get('type');

        if (token) {
            setGoogleToken(token, type);
            navigate('/dashboard');
        } else {
            navigate('/login');
        }
    }, [searchParams, navigate, setGoogleToken]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-[#09090b]">
            <div className="flex flex-col items-center gap-4">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                <p className="text-zinc-400">Completing sign in...</p>
            </div>
        </div>
    );
}
