"""
Quick start testing script for Second Brain
"""

import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from backend.config import config
from backend.ollama_service import ollama_service
from backend.memory_store import memory_store
from backend.rag_engine import rag_engine
from backend.security import security_manager


def test_ollama():
    """Test Ollama connection"""
    print("\n🔍 Testing Ollama Connection...")
    
    if ollama_service.check_connection():
        print("✅ Ollama is running!")
        
        models = ollama_service.list_models()
        print(f"📦 Available models: {models}")
        
        if config.OLLAMA_MODEL in models:
            print(f"✅ {config.OLLAMA_MODEL} is available")
        else:
            print(f"⚠️  {config.OLLAMA_MODEL} not found. Available: {models}")
            return False
        
        return True
    else:
        print("❌ Ollama is not running!")
        print("Please start Ollama first:")
        print(f"  ollama run {config.OLLAMA_MODEL}")
        return False


def test_encryption():
    """Test encryption/decryption"""
    print("\n🔐 Testing Security...")
    
    test_data = {"message": "Secret information", "value": 123}
    
    try:
        encrypted = security_manager.encrypt_data(test_data)
        print(f"✅ Encryption successful")
        
        decrypted = security_manager.decrypt_data(encrypted)
        print(f"✅ Decryption successful")
        
        if test_data == decrypted:
            print("✅ Data integrity verified")
            return True
        else:
            print("❌ Data mismatch after decryption")
            return False
    except Exception as e:
        print(f"❌ Encryption test failed: {str(e)}")
        return False


def test_memory_store():
    """Test memory store"""
    print("\n💾 Testing Memory Store...")
    
    try:
        # Add a test memory
        test_memory = "Test memory entry for verification"
        metadata = {"importance": 0.8, "tags": "test,verification"}
        
        memory_id = memory_store.store_memory(test_memory, metadata)
        print(f"✅ Memory stored with ID: {memory_id}")
        
        # Retrieve the memory
        memory = memory_store.get_memory(memory_id)
        if memory:
            print(f"✅ Memory retrieved successfully")
            print(f"   Content: {memory['content']}")
        else:
            print("❌ Failed to retrieve memory")
            return False
        
        # Delete the test memory
        if memory_store.delete_memory(memory_id):
            print(f"✅ Memory deleted successfully")
        else:
            print("❌ Failed to delete memory")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Memory store test failed: {str(e)}")
        return False


def test_rag():
    """Test RAG pipeline"""
    print("\n🤖 Testing RAG Pipeline...")
    
    try:
        # Add some sample memories
        memories = [
            "I have a meeting on Friday at 3 PM",
            "Python is my favorite programming language",
            "I like to drink coffee in the morning"
        ]
        
        memory_ids = []
        for mem in memories:
            mem_id = memory_store.store_memory(mem, {"importance": 0.7})
            memory_ids.append(mem_id)
            print(f"✅ Stored sample memory: {mem}")
        
        # Test retrieval
        query = "What meetings do I have?"
        retrieved = rag_engine.retrieve_relevant_memories(query, top_k=3)
        print(f"✅ Retrieved {len(retrieved)} relevant memories")
        
        # Test RAG response generation
        print("\n📝 Testing response generation...")
        print("   (This may take a moment...)")
        
        response = rag_engine.generate_response(query, memories=retrieved)
        if response and not response.startswith("Error"):
            print(f"✅ Generated response:")
            print(f"   {response[:100]}...")
        else:
            print(f"⚠️  Response generation warning: {response}")
        
        # Clean up
        for mem_id in memory_ids:
            memory_store.delete_memory(mem_id)
        
        return True
    except Exception as e:
        print(f"❌ RAG pipeline test failed: {str(e)}")
        return False


def test_direct_answer():
    """Test direct responses for simple temporal questions."""
    print("\n⏳ Testing direct date answer fallback...")
    try:
        today_query = "What is today's date?"
        today_response = rag_engine.generate_response(today_query, memories=[])
        expected_today = datetime.now().strftime("Today's date is %B %d, %Y.")
        if today_response.strip() != expected_today:
            print(f"❌ Unexpected today answer: {today_response}")
            return False

        tomorrow_query = "What is tomorrow's date?"
        tomorrow_response = rag_engine.generate_response(tomorrow_query, memories=[])
        expected_tomorrow = (datetime.now() + timedelta(days=1)).strftime("Tomorrow's date is %B %d, %Y.")
        if tomorrow_response.strip() != expected_tomorrow:
            print(f"❌ Unexpected tomorrow answer: {tomorrow_response}")
            return False

        print(f"✅ Direct date fallback answered correctly.")
        return True
    except Exception as e:
        print(f"❌ Direct date fallback test failed: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("🧠 Second Brain - System Verification")
    print("=" * 50)
    
    results = {}
    
    results["Ollama"] = test_ollama()
    results["Encryption"] = test_encryption()
    results["Memory Store"] = test_memory_store()
    
    # Only test RAG if Ollama is working
    if results["Ollama"]:
        results["RAG Pipeline"] = test_rag()
    else:
        print("\n⏭️  Skipping RAG test (Ollama not available)")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {test}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All systems operational! Ready to run the app.")
        print("\nRun the Streamlit app with:")
        print("  streamlit run frontend/app.py")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")


if __name__ == "__main__":
    main()
