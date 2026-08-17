import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/store/authStore';
import { Loader2 } from 'lucide-react';

export default function GoogleCallbackPage() {
    const navigate = useNavigate();
    const { verifyGoogleSession } = useAuth();

    useEffect(() => {
        const init = async () => {
            // The backend sets the HttpOnly cookie during the Google OAuth redirect.
            // Just verify the session and navigate to dashboard.
            const success = await verifyGoogleSession();
            if (success) {
                navigate('/dashboard');
            } else {
                navigate('/login');
            }
        };
        init();
    }, [navigate, verifyGoogleSession]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-[#09090b]">
            <div className="flex flex-col items-center gap-4">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                <p className="text-zinc-400">Completing sign in...</p>
            </div>
        </div>
    );
}
