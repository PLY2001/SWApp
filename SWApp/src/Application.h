#pragma once
#include <unordered_map>
#include <map>
#include <string>
#include <atlstr.h>
#include <memory>
#include <mutex>

//SolidWorks
#include <atlbase.h> //com
#import "sldworks.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids  // SOLIDWORKS type library
#import "swconst.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids   // SOLIDWORKS constants type library

namespace MyApp {



	class MyApplication {
	private:
		std::map<std::string, std::string> property;
		std::map<std::string, std::string> summary;
		bool hasProperty = false;//是否检测到属性

		std::string MyStateMessage[3] = { "Unfinished","Succeed!","Failed!" };
		enum class MyState
		{
			Nothing, Succeed, Failed
		};
		enum class SWState
		{
			Connected, FileOpen, PropertyGot,MBDGot 
		};
		std::map<SWState, MyState> SWStateMap = {
			 {SWState::Connected,   MyState::Nothing}
			,{SWState::FileOpen,    MyState::Nothing}
			,{SWState::PropertyGot, MyState::Nothing}
			,{SWState::MBDGot,      MyState::Nothing}
		};
		
		MyState myState = MyState::Nothing;

		bool toLoad = false;//是否弹出项目地址窗口


		


		
		void EnableDocking();
		void ShowMenuBar();
		void ShowImguiExample();
		bool ShowMessage(const char* message);
		//bool ShowSW();
		bool ConnectSW();
		bool OpenFile();
		bool ReadProperty();
		//bool SWBotton(const char* BottonName, SWState state, bool(MyApp::MyApplication::*func)());

		std::string GbkToUtf8(const char* src_str);

		
	public:
		void ShowMyApp();

		
		
	private:
		static std::shared_ptr<MyApplication> instance;
		
		MyApplication() {};
		~MyApplication() {};
	public:
		static MyApplication& GetInstance() {
			static MyApplication instance;
			return instance;
		}
		

	};

	


    
}
