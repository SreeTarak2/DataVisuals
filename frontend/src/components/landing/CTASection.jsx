import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

const CTASection = () => {
    return (
        <section className="py-24 bg-slate-950 px-4">
            <div className="container mx-auto max-w-5xl">
                <div className="relative rounded-3xl overflow-hidden bg-gradient-to-r from-blue-600 to-cyan-600 p-12 md:p-20 text-center shadow-2xl shadow-blue-900/40">
                    {/* Background Texture */}
                    <div className="absolute inset-0 opacity-10 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] mix-blend-overlay"></div>

                    <h2 className="text-3xl md:text-5xl font-bold text-white mb-6 relative z-10">
                        Ready to unlock your data's potential?
                    </h2>
                    <p className="text-blue-100 text-lg md:text-xl mb-10 max-w-2xl mx-auto relative z-10">
                        Join thousands of analysts and business users who are saving hours every week with DataSage AI.
                    </p>

                    <div className="relative z-10 flex flex-col sm:flex-row gap-4 justify-center">
                        <Link
                            to="/register"
                            className="inline-flex items-center justify-center px-8 py-4 text-lg font-bold text-blue-600 bg-white rounded-full hover:bg-blue-50 transition-colors shadow-lg"
                        >
                            Get Started for Free
                            <ArrowRight className="ml-2 w-5 h-5" />
                        </Link>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default CTASection;
