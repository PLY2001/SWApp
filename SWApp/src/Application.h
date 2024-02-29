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
#import "swdimxpert.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids  //SOLIDWORKS dimxpert library

namespace MyApp {



	class MyApplication {
	private:
		std::map<std::string, std::string> property;//记录自定义属性
		std::map<std::string, std::string> summary;//记录摘要
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
		};//记录SW交互状态
		MyState myState = MyState::Nothing;//记录当前操作状态

		bool toLoad = false;//是否弹出项目地址窗口
		
		long DimXpertAnnotationCount = 0;//MBD标注数
		long DimXpertFeatureCount = 0;//MVD特征数

		std::map<std::string, std::vector<std::string>> DimXpertMap;//记录MBD树(特征,(标注1，标注2...))
		bool hasMBD = false;//是否检测到MBD
		
		
		void EnableDocking();//开启Docking特性
		void ShowMenuBar();
		void ShowImguiExample();
		bool ShowMessage(const char* message);//显示ImGui弹窗，而ImGui::OpenPopup("提示")用于弹出弹窗
		bool ConnectSW();
		bool OpenFile();
		bool ReadProperty();
		bool ReadMBD();

		std::string GbkToUtf8(const char* src_str);//将SW默认文本的GBK编码转为ImGui显示文本用的Utf8编码
	
	public:
		void ShowMyApp();

	//极致简洁的单例模式，运用了static的性质
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
