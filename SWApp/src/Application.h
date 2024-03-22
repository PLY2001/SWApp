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
	
	struct MyAnnotation {
		std::string Name;
		swDimXpertAnnotationType_e Type;	
	};//标注

	struct MyFeatureFace {
		std::string Name;
		int AnnotationCount = 0;
		std::vector<MyAnnotation> AnnotationArray;
	};//特征面

	enum class MyState {
		Nothing, Succeed, Failed
	};//程序当前操作状态
	enum class SWState {
		Connected, FileOpen, PropertyGot, MBDGot
	};//SW交互状态

	class MyApplication {
	private:
		std::map<std::string, std::string> property;//记录自定义属性
		std::map<std::string, std::string> summary;//记录摘要
		bool hasProperty = false;//是否检测到属性

		std::string MyStateMessage[3] = { "Unfinished","Succeed!","Failed!" };//提示文本		
		std::map<SWState, MyState> SWStateMap = {
			 {SWState::Connected,   MyState::Nothing}
			,{SWState::FileOpen,    MyState::Nothing}
			,{SWState::PropertyGot, MyState::Nothing}
			,{SWState::MBDGot,      MyState::Nothing}
		};//记录SW交互状态
		MyState myState = MyState::Nothing;//记录程序当前操作状态

		bool toLoad = false;//是否弹出项目地址窗口
		
		long DimXpertAnnotationCount = 0;//MBD标注数
		long DimXpertFeatureCount = 0;//MBD特征数

		std::vector<MyFeatureFace> myFeatureFaceArray;//记录MBD信息(特征,(标注1，标注2...)
		bool hasMBD = false;//是否检测到MBD信息
		
		std::unordered_map<swDimXpertAnnotationType_e, int> GeoTolMap = {
			 {swDimXpertGeoTol_Angularity              ,1}
			,{swDimXpertGeoTol_Circularity			   ,1}
			,{swDimXpertGeoTol_CircularRunout		   ,1}
			,{swDimXpertGeoTol_CompositeLineProfile	   ,1}
			,{swDimXpertGeoTol_CompositePosition	   ,1}
			,{swDimXpertGeoTol_CompositeSurfaceProfile ,1}
			,{swDimXpertGeoTol_Concentricity		   ,1}
			,{swDimXpertGeoTol_Cylindricity			   ,1}
			,{swDimXpertGeoTol_Flatness				   ,1}
			,{swDimXpertGeoTol_LineProfile			   ,1}
			,{swDimXpertGeoTol_Parallelism			   ,1}
			,{swDimXpertGeoTol_Perpendicularity		   ,1}
			,{swDimXpertGeoTol_Position				   ,1}
			,{swDimXpertGeoTol_Straightness			   ,1}
			,{swDimXpertGeoTol_SurfaceProfile		   ,1}
			,{swDimXpertGeoTol_Symmetry				   ,1}
			,{swDimXpertGeoTol_Tangency				   ,1}
			,{swDimXpertGeoTol_TotalRunout			   ,1}
		};//MBD标注类型集合：形位公差
		std::unordered_map<swDimXpertAnnotationType_e, int> DimTolMap = {
			 {swDimXpertDimTol_AngleBetween            ,1}
			,{swDimXpertDimTol_ChamferDimension		   ,1}
			,{swDimXpertDimTol_CompositeDistanceBetween,1}
			,{swDimXpertDimTol_ConeAngle			   ,1}
			,{swDimXpertDimTol_CounterBore			   ,1}
			,{swDimXpertDimTol_CounterSinkAngle		   ,1}
			,{swDimXpertDimTol_CounterSinkDiameter	   ,1}
			,{swDimXpertDimTol_Depth				   ,1}
			,{swDimXpertDimTol_Diameter				   ,1}
			,{swDimXpertDimTol_DistanceBetween		   ,1}
			,{swDimXpertDimTol_Length				   ,1}
			,{swDimXpertDimTol_PatternAngleBetween	   ,1}
			,{swDimXpertDimTol_Radius				   ,1}
			,{swDimXpertDimTol_Width				   ,1}
		};//MBD标注类型集合：尺寸公差
			
		void EnableDocking();//开启Docking特性
		void ShowMenuBar();//显示菜单栏
		void ShowImguiExample();//显示Imgui示例
		bool ShowMessage(const char* message);//显示ImGui弹窗，而ImGui::OpenPopup("提示")用于弹出弹窗
		bool ConnectSW();//连接SW
		bool OpenFile();//打开文件
		bool ReadProperty();//读取属性
		bool ReadMBD();//读取MBD特征及其标注

		std::string GbkToUtf8(const char* src_str);//将SW默认文本的GBK编码转为ImGui显示文本用的Utf8编码
		bool ReadSafeArray(VARIANT* vt, VARENUM vtType, int dimensional, LPVOID* pData, LONG* itemCount);//读取SAFEARRAY数组(输入VARIANT变量，数组元素类型，数组维度，输出数组，输出数组大小)
		template<typename T>
		bool CreatVARIANTArray(int size, VARENUM type, T* buffer, VARIANT* array);//创建含SAFEARRAY的VARIANT变量(数组大小，数组元素类型，输入数组，输出VARIANT变量)
		void ReadAnnotationData(swDimXpertAnnotationType_e annoType);//读取标注数据

		void DatumData();//读取基准信息
		void GeoTolData();//读取形位公差数据
		void DimTolData(swDimXpertAnnotationType_e annoType);//读取尺寸公差数据
	
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
