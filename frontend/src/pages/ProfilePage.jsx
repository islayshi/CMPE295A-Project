import { useState } from 'react';
import Navbar from '../components/Navbar';

const ProfilePage = () => {
    const [customAddresses, setCustomAddresses] = useState([]);
    const [otherHealth, setOtherHealth] = useState(false);

    const addAddress = () => {
        if (customAddresses.length < 5) {
            setCustomAddresses([...customAddresses, { name: '', city: '', state: '', zip: '' }]);
        }
    };

    const inputClass = "w-full px-4 py-2 bg-[#222] border border-gray-700 rounded-lg focus:ring-2 focus:ring-[#7F77DD] outline-none text-white text-sm";
    const labelClass = "block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2";

    return (
        <div className="min-h-screen bg-[#111] text-white font-sans pb-20">
            <Navbar />

            <div className="max-w-3xl mx-auto pt-32 px-6">
                <h1 className="text-3xl font-bold mb-10 text-[#7F77DD]">Edit Profile</h1>

                <div className="space-y-12">
                    <section>
                        <h2 className="text-xl font-bold mb-4 text-gray-200">User Info</h2>
                        <div className="space-y-2 px-1">
                            <p className="text-gray-400">Name: <span className="text-white ml-2">[John Doe]</span></p>
                            <p className="text-gray-400">Email: <span className="text-white ml-2">[johndoe@example.com]</span></p>
                        </div>
                    </section>

                    <section>
                        <h2 className="text-xl font-bold mb-6 text-gray-200">Location Info</h2>

                        <div className="space-y-8">
                            {/* Home Address Row */}
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 bg-[#1a1a1a] rounded-xl border border-gray-800">
                                <div className="md:col-span-4"><h3 className={labelClass}>Home Address</h3></div>
                                <input className={inputClass} placeholder="Address Name" />
                                <input className={inputClass} placeholder="City" />
                                <input className={inputClass} placeholder="State" />
                                <input className={inputClass} placeholder="ZIP" />
                            </div>

                            {customAddresses.map((_, i) => (
                                <div key={i} className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 bg-[#1a1a1a] rounded-xl border border-gray-800 animate-in fade-in duration-300">
                                    <div className="md:col-span-4"><h3 className={labelClass}>Custom Address {i + 1}</h3></div>
                                    <input className={inputClass} placeholder="Address Name" />
                                    <input className={inputClass} placeholder="City" />
                                    <input className={inputClass} placeholder="State" />
                                    <input className={inputClass} placeholder="ZIP" />
                                </div>
                            ))}

                            <button
                                onClick={addAddress}
                                className="text-sm font-medium text-[#7F77DD] hover:text-[#958df0] transition-colors"
                            >
                                + Add another custom address
                            </button>
                        </div>
                    </section>

                    <section>
                        <h2 className="text-xl font-bold mb-6 text-gray-200">Health</h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-[#1a1a1a] p-6 rounded-xl border border-gray-800">
                            {[
                                "Asthma", "Immunocompromised", "Chronic Bronchitis",
                                "Cardiovascular Conditions", "Lung Cancer", "Pregnant"
                            ].map(condition => (
                                <label key={condition} className="flex items-center space-x-3 cursor-pointer group">
                                    <input type="checkbox" className="w-5 h-5 rounded border-gray-700 bg-[#222] text-[#7F77DD] focus:ring-offset-[#111]" />
                                    <span className="text-gray-300 group-hover:text-white transition-colors">{condition}</span>
                                </label>
                            ))}

                            <div className="md:col-span-2 mt-2 pt-4 border-t border-gray-800">
                                <label className="flex items-center space-x-3 cursor-pointer mb-4">
                                    <input
                                        type="checkbox"
                                        onChange={(e) => setOtherHealth(e.target.checked)}
                                        className="w-5 h-5 rounded border-gray-700 bg-[#222] text-[#7F77DD]"
                                    />
                                    <span className="text-gray-300">Other</span>
                                </label>
                                {otherHealth && (
                                    <input className={inputClass} placeholder="Please specify condition..." />
                                )}
                            </div>
                        </div>
                    </section>

                    <section>
                        <h2 className="text-xl font-bold mb-6 text-gray-200">Notification Preferences</h2>
                        <div className="bg-[#1a1a1a] p-6 rounded-xl border border-gray-800 space-y-8">

                            <div>
                                <h3 className={labelClass}>Alert Delivery Method</h3>
                                <div className="flex space-x-6">
                                    {["SMS", "Email", "Push"].map(method => (
                                        <label key={method} className="flex items-center space-x-2 cursor-pointer">
                                            <input type="checkbox" className="w-4 h-4 rounded border-gray-700 bg-[#222] text-[#7F77DD]" />
                                            <span className="text-sm text-gray-300">{method}</span>
                                        </label>
                                    ))}
                                </div>
                            </div>

                            <div className="relative max-w-xs">
                                <h3 className={labelClass}>Alert Sensitivity Method</h3>
                                <div className="relative">
                                    <select className={`${inputClass} pr-10 appearance-none cursor-pointer`}>
                                        <option>Moderate</option>
                                        <option>Only Emergencies</option>
                                    </select>

                                    {/* This is the downward arrow icon */}
                                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-400">
                                        <svg className="h-4 w-4 fill-current" viewBox="0 0 20 20">
                                            <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
                                        </svg>
                                    </div>
                                </div>
                            </div>

                        </div>
                    </section>

                    <button className="w-full py-4 bg-[#7F77DD] hover:bg-[#6b62c7] text-white font-bold rounded-xl shadow-lg transition-all active:scale-[0.98]">
                        Finished Editing
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ProfilePage;