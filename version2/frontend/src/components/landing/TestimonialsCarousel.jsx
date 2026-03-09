import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight, Quote } from 'lucide-react';

const testimonials = [
    {
        quote: "DataSage eliminated our need for a dedicated BI developer. The AI generates exactly what we need in seconds.",
        name: "Sarah Jenkins",
        role: "Head of Growth",
        company: "Acme Corp"
    },
    {
        quote: "The chart recommendations are uncanny. It always seems to know exactly how I want to look at the data before I ask.",
        name: "David Chen",
        role: "Data Analyst",
        company: "Globex"
    },
    {
        quote: "We dumped Tableau for this. The natural language interface means our sales team can finally pull their own reports.",
        name: "Elena Rodriguez",
        role: "VP of Sales",
        company: "TechNova"
    }
];

const TestimonialsCarousel = () => {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [direction, setDirection] = useState(0);

    const slideVariants = {
        enter: (direction) => {
            return {
                x: direction > 0 ? 1000 : -1000,
                opacity: 0
            };
        },
        center: {
            zIndex: 1,
            x: 0,
            opacity: 1
        },
        exit: (direction) => {
            return {
                zIndex: 0,
                x: direction < 0 ? 1000 : -1000,
                opacity: 0
            };
        }
    };

    const swipeConfidenceThreshold = 10000;
    const swipePower = (offset, velocity) => {
        return Math.abs(offset) * velocity;
    };

    const paginate = (newDirection) => {
        setDirection(newDirection);
        setCurrentIndex((prevIndex) => {
            let nextIndex = prevIndex + newDirection;
            if (nextIndex < 0) nextIndex = testimonials.length - 1;
            if (nextIndex >= testimonials.length) nextIndex = 0;
            return nextIndex;
        });
    };

    // Auto-advance
    useEffect(() => {
        const timer = setInterval(() => {
            paginate(1);
        }, 8000);
        return () => clearInterval(timer);
    }, [currentIndex]);

    return (
        <section id="testimonials" className="py-32 relative">
            <div className="container mx-auto px-6 max-w-4xl relative z-10">
                <div className="text-center mb-16">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.5 }}
                        className="text-3xl md:text-5xl font-bold tracking-tight mb-6"
                    >
                        Loved by Data Teams
                    </motion.h2>
                </div>

                <div className="relative h-[300px] md:h-[250px] flex items-center justify-center overflow-hidden">
                    <AnimatePresence initial={false} custom={direction}>
                        <motion.div
                            key={currentIndex}
                            custom={direction}
                            variants={slideVariants}
                            initial="enter"
                            animate="center"
                            exit="exit"
                            transition={{
                                x: { type: "spring", stiffness: 300, damping: 30 },
                                opacity: { duration: 0.2 }
                            }}
                            drag="x"
                            dragConstraints={{ left: 0, right: 0 }}
                            dragElastic={1}
                            onDragEnd={(e, { offset, velocity }) => {
                                const swipe = swipePower(offset.x, velocity.x);
                                if (swipe < -swipeConfidenceThreshold) {
                                    paginate(1);
                                } else if (swipe > swipeConfidenceThreshold) {
                                    paginate(-1);
                                }
                            }}
                            className="absolute w-full px-4 md:px-12"
                        >
                            <div className="flex flex-col items-center text-center">
                                <Quote className="w-10 h-10 text-sky-400/50 mb-6" />
                                <p className="text-xl md:text-3xl font-medium text-slate-100 mb-8 leading-tight text-balance">
                                    "{testimonials[currentIndex].quote}"
                                </p>
                                <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-sky-500 to-purple-500 flex items-center justify-center text-white font-bold text-lg">
                                        {testimonials[currentIndex].name.charAt(0)}
                                    </div>
                                    <div className="text-left">
                                        <div className="font-semibold text-slate-50">{testimonials[currentIndex].name}</div>
                                        <div className="text-sm text-slate-400">{testimonials[currentIndex].role}, {testimonials[currentIndex].company}</div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </AnimatePresence>

                    {/* Controls */}
                    <button
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-slate-900/80 border border-white/10 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800 transition-colors z-20"
                        onClick={() => paginate(-1)}
                        aria-label="Previous testimonial"
                    >
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                    <button
                        className="absolute right-0 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-slate-900/80 border border-white/10 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800 transition-colors z-20"
                        onClick={() => paginate(1)}
                        aria-label="Next testimonial"
                    >
                        <ChevronRight className="w-5 h-5" />
                    </button>
                </div>

                {/* Dots */}
                <div className="flex justify-center gap-2 mt-8">
                    {testimonials.map((_, idx) => (
                        <button
                            key={idx}
                            onClick={() => {
                                setDirection(idx > currentIndex ? 1 : -1);
                                setCurrentIndex(idx);
                            }}
                            className={`w-2 h-2 rounded-full transition-all ${idx === currentIndex ? 'bg-sky-400 w-6' : 'bg-slate-700'}`}
                            aria-label={`Go to slide ${idx + 1}`}
                        />
                    ))}
                </div>
            </div>
        </section>
    );
};

export default TestimonialsCarousel;
