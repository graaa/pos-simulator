import React, { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://64.227.83.209:8001'

export default function App(){
  const [menuItems, setMenuItems] = useState([])
  const [selectedItems, setSelectedItems] = useState([])
  const [table, setTable] = useState('Mesa 1')
  const [order, setOrder] = useState(null)
  const [tip, setTip] = useState(0)
  const [txn, setTxn] = useState(null)
  const [selectedCategory, setSelectedCategory] = useState('All')

  const subtotal = selectedItems.reduce((s,i)=> s + i.qty*i.price, 0)

  // Load menu items on component mount
  useEffect(() => {
    fetch(`${API}/items`)
      .then(res => res.json())
      .then(data => setMenuItems(data))
      .catch(err => console.error('Error loading menu:', err))
  }, [])

  async function createOrder(){
    const r = await fetch(`${API}/orders`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ table, items: selectedItems })
    })
    const data = await r.json()
    setOrder(data)
    setTxn(null)
  }

  async function charge(){
    if(!order) return
    const r = await fetch(`${API}/payments/charge`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ order_id: order.id, tip: Number(tip)||0 })
    })
    const data = await r.json()
    setTxn(data)
  }

  function addToOrder(menuItem){
    const existingItem = selectedItems.find(item => item.name === menuItem.name)
    if (existingItem) {
      updateItemQuantity(menuItem.name, existingItem.qty + 1)
    } else {
      setSelectedItems([...selectedItems, { 
        name: menuItem.name, 
        qty: 1, 
        price: menuItem.price 
      }])
    }
  }

  function updateItemQuantity(itemName, newQty){
    if (newQty <= 0) {
      setSelectedItems(selectedItems.filter(item => item.name !== itemName))
    } else {
      setSelectedItems(selectedItems.map(item => 
        item.name === itemName ? { ...item, qty: newQty } : item
      ))
    }
  }

  function removeFromOrder(itemName){
    setSelectedItems(selectedItems.filter(item => item.name !== itemName))
  }

  const categories = ['All', ...new Set(menuItems.map(item => item.category))]
  const filteredItems = selectedCategory === 'All' 
    ? menuItems 
    : menuItems.filter(item => item.category === selectedCategory)

  return (
    <div style={{maxWidth: 1200, margin: '40px auto', fontFamily: 'system-ui, sans-serif'}}>
      <h1>🍽️ Restaurante Tico POS</h1>

      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px'}}>
        {/* Menu Section */}
        <section style={{padding:12, border:'1px solid #ddd', borderRadius:8, marginBottom:16}}>
          <h3>📋 Menu</h3>
          <div style={{marginBottom: 12}}>
            <label>Category:&nbsp;
              <select value={selectedCategory} onChange={e=>setSelectedCategory(e.target.value)}>
                {categories.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </label>
          </div>
          <div style={{maxHeight: '400px', overflowY: 'auto'}}>
            {filteredItems.map((item) => (
              <div key={item.id} style={{
                padding: '8px', 
                border: '1px solid #eee', 
                borderRadius: '4px', 
                marginBottom: '8px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <div style={{fontWeight: 'bold'}}>{item.name}</div>
                  <div style={{fontSize: '12px', color: '#666'}}>{item.description}</div>
                  <div style={{fontWeight: 'bold', color: '#2c5aa0'}}>₡{item.price.toFixed(2)}</div>
                </div>
                <button 
                  onClick={() => addToOrder(item)}
                  style={{
                    padding: '4px 8px',
                    backgroundColor: '#4caf50',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  + Add
                </button>
              </div>
            ))}
          </div>
        </section>

        {/* Order Section */}
        <section style={{padding:12, border:'1px solid #ddd', borderRadius:8, marginBottom:16}}>
          <h3>🛒 Order</h3>
          <label>Table:&nbsp;
            <input value={table} onChange={e=>setTable(e.target.value)} />
          </label>
          <div style={{marginTop:8}}>
            {selectedItems.length === 0 ? (
              <p style={{color: '#666', fontStyle: 'italic'}}>No items selected</p>
            ) : (
              selectedItems.map((item, idx) => (
                <div key={idx} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px',
                  border: '1px solid #eee',
                  borderRadius: '4px',
                  marginBottom: '6px'
                }}>
                  <div>
                    <div style={{fontWeight: 'bold'}}>{item.name}</div>
                    <div style={{fontSize: '12px', color: '#666'}}>₡{item.price.toFixed(2)} each</div>
                  </div>
                  <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <button 
                      onClick={() => updateItemQuantity(item.name, item.qty - 1)}
                      style={{padding: '2px 6px', fontSize: '12px'}}
                    >-</button>
                    <span>{item.qty}</span>
                    <button 
                      onClick={() => updateItemQuantity(item.name, item.qty + 1)}
                      style={{padding: '2px 6px', fontSize: '12px'}}
                    >+</button>
                    <button 
                      onClick={() => removeFromOrder(item.name)}
                      style={{
                        padding: '2px 6px', 
                        fontSize: '12px',
                        backgroundColor: '#f44336',
                        color: 'white',
                        border: 'none',
                        borderRadius: '2px'
                      }}
                    >×</button>
                  </div>
                </div>
              ))
            )}
          </div>
          <div style={{marginTop:8, fontWeight: 'bold'}}>Subtotal: ₡{subtotal.toFixed(2)}</div>
          <button 
            style={{marginTop:8, padding: '8px 16px'}} 
            onClick={createOrder}
            disabled={selectedItems.length === 0}
          >
            Create Order
          </button>
        </section>
      </div>

      {order && (
        <section style={{padding:12, border:'1px solid #ddd', borderRadius:8, marginBottom:16}}>
          <h3>Payment</h3>
          <div>Order #{order.id} — Total now (subtotal + tip)</div>
          <label>Tip: ₡ <input type="number" value={tip} onChange={e=>setTip(e.target.value)} /></label>
          <div style={{marginTop:8}}>
            <button onClick={charge}>Charge on terminal</button>
          </div>
        </section>
      )}

      {txn && (
        <section style={{padding:12, border:'1px solid #4caf50', borderRadius:8}}>
          <h3>Result</h3>
          <pre>{JSON.stringify(txn, null, 2)}</pre>
          <p style={{fontSize:12, color:'#555'}}>Note: Only status/auth_code/masked_card/terminal_ref are returned — no PAN/CVV handled by POS.</p>
        </section>
      )}
    </div>
  )
}
