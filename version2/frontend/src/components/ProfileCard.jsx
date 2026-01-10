import React from 'react';
import { motion } from 'framer-motion';
import { 
  MapPin, Link as LinkIcon, Twitter, Github, Linkedin, 
  Mail, Calendar, Award, Zap, Activity 
} from 'lucide-react';

const ProfileCard = ({ user }) => {
  // Placeholder data if not provided in user object
  const userData = {
    name: user?.full_name || 'Alex Quant',
    role: user?.role || 'Senior Data Architect',
    location: 'San Francisco, CA',
    joinDate: 'Joined Jan 2024',
    bio: 'Building the future of data visualization. Passionate about AI, quantum computing, and creating intuitive user experiences.',
    avatar: user?.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=Felix',
    stats: [
      { label: 'Projects', value: '142', icon: Zap, color: 'text-yellow-400' },
      { label: 'Contests', value: '28', icon: Award, color: 'text-purple-400' },
      { label: 'Rank', value: '#4', icon: Activity, color: 'text-green-400' },
    ],
    socials: [
      { icon: Github, href: '#', label: 'GitHub' },
      { icon: Twitter, href: '#', label: 'Twitter' },
      { icon: Linkedin, href: '#', label: 'LinkedIn' },
      { icon: Mail, href: '#', label: 'Email' },
    ]
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="relative w-full max-w-md mx-auto"
    >
      {/* Abstract Background Glow */}
      <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-2xl blur opacity-30 group-hover:opacity-50 transition duration-1000 group-hover:duration-200" />
      
      <div className="relative overflow-hidden rounded-2xl bg-slate-900/90 border border-white/10 shadow-2xl backdrop-blur-xl">
        
        {/* Banner / Header Background */}
        <div className="h-32 bg-gradient-to-br from-slate-800 to-slate-900 relative">
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/90 to-transparent"></div>
        </div>

        <div className="px-6 pb-8 relative">
          {/* Avatar */}
          <div className="relative -mt-16 mb-4 flex justify-between items-end">
            <motion.div 
              whileHover={{ scale: 1.05 }}
              className="relative"
            >
              <div className="w-32 h-32 rounded-2xl p-1 bg-gradient-to-br from-cyan-400 to-purple-500 shadow-lg">
                <img 
                  src={userData.avatar} 
                  alt={userData.name} 
                  className="w-full h-full rounded-xl bg-slate-950 object-cover"
                />
              </div>
              <div className="absolute -bottom-2 -right-2 bg-slate-900 rounded-full p-1.5 border border-white/10">
                <div className="w-4 h-4 rounded-full bg-green-500 border-2 border-slate-900 animate-pulse"></div>
              </div>
            </motion.div>
            
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 border border-white/10 text-white text-sm font-medium transition-all backdrop-blur-md"
            >
              Edit Profile
            </motion.button>
          </div>

          {/* User Info */}
          <div className="space-y-4">
            <div>
              <h2 className="text-2xl font-bold text-white tracking-tight">{userData.name}</h2>
              <p className="text-cyan-400 font-medium">{userData.role}</p>
            </div>

            <div className="flex flex-wrap gap-4 text-sm text-slate-400">
              <div className="flex items-center gap-1.5">
                <MapPin className="w-4 h-4" />
                {userData.location}
              </div>
              <div className="flex items-center gap-1.5">
                <Calendar className="w-4 h-4" />
                {userData.joinDate}
              </div>
            </div>

            <p className="text-slate-300 leading-relaxed text-sm">
              {userData.bio}
            </p>

            {/* Stats Grid */}
            <div className="grid grid-cols-3 gap-3 py-4">
              {userData.stats.map((stat, index) => (
                <div key={index} className="p-3 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition-colors text-center group">
                  <stat.icon className={`w-5 h-5 mx-auto mb-1 ${stat.color}`} />
                  <div className="text-lg font-bold text-white">{stat.value}</div>
                  <div className="text-xs text-slate-400">{stat.label}</div>
                </div>
              ))}
            </div>

            {/* Social Links */}
            <div className="pt-4 border-t border-white/10 flex gap-3">
              {userData.socials.map((social, index) => (
                <motion.a
                  key={index}
                  href={social.href}
                  whileHover={{ y: -2, color: '#fff' }}
                  className="p-2 rounded-lg bg-white/5 hover:bg-cyan-500/20 text-slate-400 hover:text-cyan-400 transition-all border border-transparent hover:border-cyan-500/30"
                >
                  <social.icon className="w-5 h-5" />
                </motion.a>
              ))}
              <motion.button
                whileHover={{ y: -2 }}
                className="ml-auto flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-medium shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 transition-all"
              >
                Connect
              </motion.button>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default ProfileCard;
