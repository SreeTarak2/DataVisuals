import React from 'react';
import ProfileCard from '../../components/ProfileCard';

const Profile = () => {
    return (
        <div className="min-h-full bg-[#020203] flex items-start justify-center p-6 pt-8">
            <div className="w-full max-w-xl">
                <ProfileCard />
            </div>
        </div>
    );
};

export default Profile;
