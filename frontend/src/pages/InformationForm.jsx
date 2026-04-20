import { useState } from 'react';
import Navbar from '../components/Navbar';

const InformationForm = () => {
    const [customAddresses, setCustomAddresses] = useState([]);
    const [otherText, setOtherText] = useState(""); // <--- FIX 1: ADD THIS MISSING STATE
    const [conditions, setConditions] = useState({
        "Asthma": false,
        "Immunocompromised": false,
        "Chronic Bronchitis": false,
        "Cardiovascular": false,
        "Lung Cancer": false,
        "Pregnant": false,
        "other": false, // Keep this lowercase
    });

    const addAddressField = () => {
        if (customAddresses.length < 5) {
            setCustomAddresses([...customAddresses, { name: '', state: '', zip: '' }]);
        }
    };

    const styles = {
        wrapper: {
            paddingTop: '100px',
            paddingBottom: '50px',
            minHeight: '100vh',
            backgroundColor: '#f8fafc',
            fontFamily: "'Inter', sans-serif",
        },
        container: {
            maxWidth: '800px',
            margin: '0 auto',
            padding: '0 20px',
        },
        section: {
            backgroundColor: 'white',
            padding: '40px',
            borderRadius: '16px',
            marginBottom: '30px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
            border: '1px solid #f1f5f9',
        },
        header: { fontSize: '1.5rem', color: '#0f172a', marginBottom: '8px' },
        subText: { color: '#64748b', marginBottom: '24px' },
        addressGroup: {
            display: 'grid',
            gridTemplateColumns: '2fr 1fr 1fr',
            gap: '16px',
            marginBottom: '20px',
        },
        input: {
            width: '100%',
            boxSizing: 'border-box',
            padding: '14px',
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '10px',
            fontSize: '1rem',
        },
        checkboxGrid: {
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '15px',
        },
        checkboxItem: {
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            cursor: 'pointer',
        },
        submitBtn: {
            width: '100%',
            backgroundColor: '#2a9d8f',
            color: 'white',
            padding: '18px',
            border: 'none',
            borderRadius: '12px',
            fontSize: '1.1rem',
            fontWeight: '700',
            cursor: 'pointer',
        }
    };

    return (
        <div style={styles.wrapper}>
            <Navbar />
            <div style={styles.container}>
                <form onSubmit={(e) => e.preventDefault()}>

                    <section style={styles.section}>
                        <h2 style={styles.header}>Location Info</h2>
                        <p style={styles.subText}>Enter your primary and secondary locations.</p>

                        <h3>Home Address</h3>
                        <div style={styles.addressGroup}>
                            <input style={styles.input} type="text" placeholder="Address Name" />
                            <input style={styles.input} type="text" placeholder="State" />
                            <input style={styles.input} type="text" placeholder="ZIP" />
                        </div>

                        {customAddresses.map((_, i) => (
                            <div key={i} style={{ ...styles.addressGroup, borderTop: '1px solid #eee', paddingTop: '20px' }}>
                                <input style={styles.input} type="text" placeholder="Custom Name" />
                                <input style={styles.input} type="text" placeholder="State" />
                                <input style={styles.input} type="text" placeholder="ZIP" />
                            </div>
                        ))}

                        {customAddresses.length < 5 && (
                            <button type="button" onClick={addAddressField} style={{ ...styles.submitBtn, backgroundColor: '#f1f5f9', color: '#64748b', marginTop: '10px' }}>
                                + Add Address
                            </button>
                        )}
                    </section>

                    <section style={styles.section}>
                        <h2 style={styles.header}>Health</h2>
                        <p style={styles.subText}>Existing Health Conditions?</p>

                        <div style={styles.checkboxGrid}>
                            {Object.keys(conditions).map((key) => (
                                <label key={key} style={styles.checkboxItem}>
                                    <input
                                        type="checkbox"
                                        checked={conditions[key]}
                                        onChange={(e) => setConditions({ ...conditions, [key]: e.target.checked })}
                                    />
                                    {key === "other" ? "Other (type below)" : key}
                                </label>
                            ))}
                        </div>

                        {/* FIX 2: Check for conditions.other (lowercase) */}
                        {conditions.other && (
                            <div style={{ marginTop: '20px' }}>
                                <label style={{ display: 'block', marginBottom: '8px', color: '#64748b' }}>
                                    Please specify other conditions:
                                </label>
                                <input
                                    style={styles.input}
                                    type="text"
                                    placeholder="Enter condition..."
                                    value={otherText}
                                    onChange={(e) => setOtherText(e.target.value)}
                                />
                            </div>
                        )}
                    </section>

                    <button type="submit" style={styles.submitBtn}>Save Information</button>
                </form>
            </div>
        </div>
    );
};

export default InformationForm;